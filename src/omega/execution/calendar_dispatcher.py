"""Privacy-first calendar operations routed through Omega's safety gateway."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from omega.calendar import (
    CalendarError,
    CalendarEvent,
    CalendarProviderError,
    CalendarProviderTimeout,
    CalendarSearchCriteria,
    CalendarService,
    CalendarValidationError,
    EventUpdateRequest,
    InvitationResponse,
    RecurrenceScope,
)
from omega.calendar.agenda import format_event, summarize_agenda
from omega.calendar.time_utils import day_range, event_times, week_range
from omega.models import (
    Action,
    ActionResult,
    ConfirmationStatus,
    ErrorCategory,
    IntentType,
    OmegaErrorDetails,
    PermissionDecision,
    RiskLevel,
    UserCommand,
)
from omega.models._serialization import JsonValue
from omega.safety import (
    ConfirmationSpec,
    GatewayDispatchResult,
    ResourceFingerprint,
    SafeExecutionGateway,
    SafetyContext,
)
from omega.understanding.result import CommandParseResult

_READ = frozenset(
    {
        IntentType.CALENDAR_STATUS,
        IntentType.LIST_CALENDAR_EVENTS,
        IntentType.SEARCH_CALENDAR_EVENTS,
        IntentType.READ_CALENDAR_EVENT,
        IntentType.SHOW_CALENDAR_AVAILABILITY,
        IntentType.SHOW_CALENDAR_AGENDA,
    }
)
_MUTATION = frozenset(
    {
        IntentType.CREATE_CALENDAR_EVENT,
        IntentType.UPDATE_CALENDAR_EVENT,
        IntentType.DELETE_CALENDAR_EVENT,
        IntentType.RESPOND_CALENDAR_INVITATION,
    }
)


@dataclass(frozen=True)
class CalendarDispatchResult:
    command: UserCommand
    action: Action
    result: ActionResult

    @property
    def user_message(self) -> str:
        return self.result.user_message

    @classmethod
    def from_gateway(cls, value: GatewayDispatchResult) -> CalendarDispatchResult:
        return cls(value.command, value.action, value.result)


class CalendarActionDispatcher:
    def __init__(
        self,
        service: CalendarService,
        gateway: SafeExecutionGateway,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self.service = service
        self.gateway = gateway
        self.clock = clock

    def dispatch(self, parsed: CommandParseResult) -> CalendarDispatchResult | None:
        original = parsed.command
        if (
            not parsed.matched
            or parsed.requires_clarification
            or original.intent not in _READ | _MUTATION
        ):
            return None
        command = self._redacted(original)
        session_id = original.session_id or UUID(int=0)
        action = Action(
            command.command_id,
            command.intent,
            parameters={
                "calendar_operation": command.intent.value,
                "content_persisted": False,
                "external_side_effect": command.intent in _MUTATION,
            },
            risk_level=RiskLevel.HIGH if command.intent in _MUTATION else RiskLevel.LOW,
            permission_decision=PermissionDecision.ALLOW,
            confirmation_status=ConfirmationStatus.NOT_REQUIRED,
            requires_confirmation=False,
        )
        try:
            target, confirmation = self._prepare(original, session_id)
        except CalendarError as error:
            return CalendarDispatchResult(
                command,
                action,
                self._failure(
                    command,
                    action,
                    "CALENDAR_PREPARATION_FAILED",
                    str(error),
                    ErrorCategory.VALIDATION,
                ),
            )
        context = SafetyContext(
            command,
            action,
            session_id,
            logical_source=target.event_id if target else command.intent.value,
            target_type="calendar_event",
            target_exists=(
                target is not None
                and original.intent is not IntentType.CREATE_CALENDAR_EVENT
            ),
            additional_context={
                "calendar_content_persisted": False,
                "credentials_present": False,
                "bulk_operation": False,
                "shell_like": False,
            },
        )
        is_create = original.intent is IntentType.CREATE_CALENDAR_EVENT
        result = self.gateway.submit(
            context,
            lambda: self._execute(original, action),
            confirmation=confirmation,
            fingerprint=None if is_create else self._fingerprint(target),
            revalidator=(
                (lambda: None)
                if is_create
                else lambda: self._revalidate(session_id, target)
            ),
        )
        return CalendarDispatchResult.from_gateway(result)

    def clear_session(self, session_id: UUID | None) -> None:
        self.service.clear_session(session_id)

    def _prepare(
        self, command: UserCommand, session_id: UUID
    ) -> tuple[CalendarEvent | None, ConfirmationSpec | None]:
        intent = command.intent
        if intent is IntentType.CREATE_CALENDAR_EVENT:
            start, end = event_times(
                self._text(command, "event_day") or "today",
                self._required(command, "event_time"),
                self._number(command, "duration_minutes") or 60,
                self.clock(),
                self.service.configuration.timezone_name,
            )
            event = CalendarEvent(
                "primary",
                self._required(command, "event_title"),
                start,
                end,
                timezone_name=self.service.configuration.timezone_name,
            )
            proposal = self.service.propose_create(session_id, event)
            conflicts = self.service.conflicts(event)
            phrase = f"confirm create event {proposal.proposal_id}"
            conflict_note = (
                "\nWarning: the provider reports a conflicting busy interval."
                if conflicts
                else "\nNo provider conflict was found for this interval."
            )
            return event, ConfirmationSpec(
                proposal.proposal_id,
                "Review this event proposal:\n"
                f"{format_event(event, event.timezone_name)}\n"
                f"{conflict_note}\n"
                f'Type "{phrase}" to create it once.',
                phrase,
                f"cancel create event {proposal.proposal_id}",
            )
        if intent in {
            IntentType.UPDATE_CALENDAR_EVENT,
            IntentType.DELETE_CALENDAR_EVENT,
            IntentType.RESPOND_CALENDAR_INVITATION,
        }:
            target = self.service.read_event(session_id)
            if intent is IntentType.UPDATE_CALENDAR_EVENT:
                title = self._text(command, "event_title")
                request = EventUpdateRequest(
                    target.event_id,
                    title=title or target.title,
                    scope=self._scope(command),
                )
                self.service.propose_update(session_id, request)
                phrase = f"confirm update event {target.event_id}"
                message = (
                    "Review the event update:\n"
                    f"{format_event(target, target.timezone_name)}\n"
                    f'Type "{phrase}".'
                )
            elif intent is IntentType.DELETE_CALENDAR_EVENT:
                if target.recurrence and self._scope(command) is None:
                    raise CalendarValidationError(
                        "Choose this event, this and future, or all events."
                    )
                phrase = f"confirm delete event {target.event_id}"
                message = (
                    "Delete this calendar event?\n"
                    f"{format_event(target, target.timezone_name)}\n"
                    f'Type "{phrase}".'
                )
            else:
                response = self._required(command, "invitation_response")
                phrase = f"confirm {response} invitation {target.event_id}"
                message = (
                    f"Respond {response} to this invitation?\n"
                    f"{format_event(target, target.timezone_name)}\n"
                    f'Type "{phrase}".'
                )
            return target, ConfirmationSpec(
                target.event_id,
                message,
                phrase,
                f"cancel calendar operation {target.event_id}",
            )
        return None, None

    def _execute(self, command: UserCommand, action: Action) -> ActionResult:
        try:
            return self._execute_validated(command, action)
        except CalendarProviderTimeout:
            return self._failure(
                command,
                action,
                "CALENDAR_PROVIDER_TIMEOUT_AMBIGUOUS",
                "The calendar provider timed out. The mutation status is uncertain, "
                "so Omega will not retry automatically.",
                ErrorCategory.TIMEOUT,
            )
        except CalendarProviderError:
            return self._failure(
                command,
                action,
                "CALENDAR_PROVIDER_FAILED",
                "The calendar provider could not complete the request. Sensitive "
                "details were omitted.",
                ErrorCategory.EXECUTION,
            )
        except CalendarError as error:
            return self._failure(
                command,
                action,
                "CALENDAR_OPERATION_FAILED",
                str(error),
                ErrorCategory.EXECUTION,
            )
        except Exception as error:
            return self._failure(
                command,
                action,
                "CALENDAR_RESPONSE_INVALID",
                "The calendar provider returned an invalid response.",
                ErrorCategory.INTERNAL,
                diagnostic=type(error).__name__,
            )

    def _execute_validated(self, command: UserCommand, action: Action) -> ActionResult:
        session_id = command.session_id or UUID(int=0)
        intent = command.intent
        if intent is IntentType.CALENDAR_STATUS:
            return self._success(action, self.service.status(), {})
        start, end = self._range(command)
        criteria = CalendarSearchCriteria(
            start,
            end,
            self._text(command, "calendar_query"),
            self.service.configuration.maximum_events_per_request,
        )
        if intent in {
            IntentType.LIST_CALENDAR_EVENTS,
            IntentType.SEARCH_CALENDAR_EVENTS,
            IntentType.SHOW_CALENDAR_AGENDA,
        }:
            page = (
                self.service.search(session_id, criteria)
                if intent is IntentType.SEARCH_CALENDAR_EVENTS
                else self.service.list_events(session_id, criteria)
            )
            return self._success(
                action,
                summarize_agenda(page.items, self.service.configuration.timezone_name),
                {"count": len(page.items)},
            )
        if intent is IntentType.READ_CALENDAR_EVENT:
            event = self.service.read_event(
                session_id, self._number(command, "event_reference")
            )
            return self._success(
                action,
                format_event(event, self.service.configuration.timezone_name),
                {"event_id": event.event_id},
            )
        if intent is IntentType.SHOW_CALENDAR_AVAILABILITY:
            busy = self.service.availability(criteria)
            free = self.service.free_intervals(criteria)
            text = (
                "You are free in that period."
                if not busy
                else "Busy intervals:\n"
                + "\n".join(
                    f"- {item.start_at.isoformat()} to {item.end_at.isoformat()}"
                    for item in busy
                )
            )
            if busy and free:
                text += "\nAlternative free intervals:\n" + "\n".join(
                    f"- {item.start_at.isoformat()} to {item.end_at.isoformat()}"
                    for item in free[:5]
                )
            return self._success(
                action,
                text,
                {"busy_count": len(busy), "free_count": len(free)},
            )
        if intent is IntentType.CREATE_CALENDAR_EVENT:
            outcome = self.service.commit_create(session_id, str(action.action_id))
            return self._success(
                action,
                "The confirmed event was created once.",
                {"operation_id": outcome.operation_id},
            )
        if intent is IntentType.UPDATE_CALENDAR_EVENT:
            outcome = self.service.commit_update(session_id, str(action.action_id))
            return self._success(
                action,
                "The confirmed event update was applied once.",
                {"operation_id": outcome.operation_id},
            )
        if intent is IntentType.DELETE_CALENDAR_EVENT:
            outcome = self.service.delete_selected(
                session_id, self._scope(command), str(action.action_id)
            )
            return self._success(
                action,
                "The confirmed event was deleted once.",
                {"operation_id": outcome.operation_id},
            )
        if intent is IntentType.RESPOND_CALENDAR_INVITATION:
            response = InvitationResponse(
                self._required(command, "invitation_response")
            )
            outcome = self.service.respond(session_id, response, str(action.action_id))
            return self._success(
                action,
                "The confirmed invitation response was submitted once.",
                {"operation_id": outcome.operation_id},
            )
        raise CalendarValidationError("That calendar operation is unavailable.")

    def _range(self, command: UserCommand) -> tuple[datetime, datetime]:
        period = self._text(command, "calendar_period") or "today"
        clock = self._text(command, "event_time")
        if command.intent is IntentType.SHOW_CALENDAR_AVAILABILITY and clock:
            return event_times(
                period,
                clock,
                30,
                self.clock(),
                self.service.configuration.timezone_name,
            )
        return (
            week_range(self.clock(), self.service.configuration.timezone_name)
            if period == "this week"
            else day_range(
                period, self.clock(), self.service.configuration.timezone_name
            )
        )

    def _revalidate(
        self, session_id: UUID, target: CalendarEvent | None
    ) -> ResourceFingerprint | None:
        if target is None:
            return None
        try:
            current = self.service.read_event(session_id)
        except CalendarError:
            return ResourceFingerprint("calendar_event", "missing", False)
        return self._fingerprint(current)

    @staticmethod
    def _fingerprint(event: CalendarEvent | None) -> ResourceFingerprint | None:
        return (
            ResourceFingerprint(
                "calendar_event", f"{event.event_id}:{event.etag}", True
            )
            if event
            else None
        )

    @staticmethod
    def _redacted(command: UserCommand) -> UserCommand:
        text = f"[calendar command: {command.intent.value}]"
        return UserCommand(
            text,
            command_id=command.command_id,
            normalized_text=text,
            intent=command.intent,
            entities=[],
            confidence=command.confidence,
            received_at=command.received_at,
            source=command.source,
            session_id=command.session_id,
            metadata={"privacy_redacted": True, "calendar_content_persisted": False},
        )

    @staticmethod
    def _text(command: UserCommand, name: str) -> str | None:
        return next(
            (
                item.value
                for item in command.entities
                if item.name == name and isinstance(item.value, str)
            ),
            None,
        )

    @classmethod
    def _required(cls, command: UserCommand, name: str) -> str:
        value = cls._text(command, name)
        if value is None:
            raise CalendarValidationError(f"{name} is required.")
        return value

    @staticmethod
    def _number(command: UserCommand, name: str) -> int | None:
        return next(
            (
                item.value
                for item in command.entities
                if item.name == name
                and isinstance(item.value, int)
                and not isinstance(item.value, bool)
            ),
            None,
        )

    @classmethod
    def _scope(cls, command: UserCommand) -> RecurrenceScope | None:
        value = cls._text(command, "recurrence_scope")
        return RecurrenceScope(value) if value else None

    @staticmethod
    def _success(
        action: Action, message: str, data: dict[str, JsonValue]
    ) -> ActionResult:
        return ActionResult.success_result(
            action.action_id, "Calendar operation completed.", message, data=data
        )

    @staticmethod
    def _failure(
        command: UserCommand,
        action: Action,
        code: str,
        user_message: str,
        category: ErrorCategory,
        *,
        diagnostic: str = "Calendar operation failed safely.",
    ) -> ActionResult:
        error = OmegaErrorDetails(
            code,
            category,
            diagnostic,
            user_message,
            True,
            details={"sensitive_details_omitted": True},
            action_id=action.action_id,
            command_id=command.command_id,
        )
        return ActionResult.failure_result(
            action.action_id, diagnostic, user_message, error
        )
