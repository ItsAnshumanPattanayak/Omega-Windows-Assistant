"""Scheduling proposals routed exclusively through Omega's central gateway."""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from uuid import UUID

from omega.models import (
    Action,
    ActionResult,
    ConfirmationStatus,
    IntentType,
    PermissionDecision,
    RiskLevel,
    UserCommand,
)
from omega.models._serialization import JsonValue
from omega.safety import GatewayDispatchResult, SafeExecutionGateway, SafetyContext
from omega.safety.models import ResourceFingerprint
from omega.scheduling import (
    RecurrenceFrequency,
    RecurrenceRule,
    ScheduledItem,
    ScheduleType,
    SchedulingService,
    configured_timezone,
    local_datetime_to_utc,
)
from omega.understanding.result import CommandParseResult

_CREATE = {
    IntentType.CREATE_REMINDER: ScheduleType.REMINDER,
    IntentType.CREATE_RECURRING_REMINDER: ScheduleType.REMINDER,
    IntentType.CREATE_ALARM: ScheduleType.ALARM,
    IntentType.CREATE_RECURRING_ALARM: ScheduleType.ALARM,
    IntentType.START_TIMER: ScheduleType.TIMER,
}
_LIST = {
    IntentType.LIST_REMINDERS: ScheduleType.REMINDER,
    IntentType.LIST_ALARMS: ScheduleType.ALARM,
    IntentType.LIST_TIMERS: ScheduleType.TIMER,
    IntentType.LIST_SCHEDULED_ITEMS: None,
}
_SHOW = {
    IntentType.SHOW_REMINDER: ScheduleType.REMINDER,
    IntentType.SHOW_ALARM: ScheduleType.ALARM,
    IntentType.SHOW_TIMER: ScheduleType.TIMER,
}
_UPDATE = {
    IntentType.UPDATE_REMINDER: ScheduleType.REMINDER,
    IntentType.UPDATE_ALARM: ScheduleType.ALARM,
}
_MUTATE = {
    IntentType.CANCEL_REMINDER: (ScheduleType.REMINDER, "cancel"),
    IntentType.COMPLETE_REMINDER: (ScheduleType.REMINDER, "complete"),
    IntentType.SNOOZE_REMINDER: (ScheduleType.REMINDER, "snooze"),
    IntentType.CANCEL_ALARM: (ScheduleType.ALARM, "cancel"),
    IntentType.DISMISS_ALARM: (ScheduleType.ALARM, "dismiss"),
    IntentType.SNOOZE_ALARM: (ScheduleType.ALARM, "snooze"),
    IntentType.PAUSE_TIMER: (ScheduleType.TIMER, "pause"),
    IntentType.RESUME_TIMER: (ScheduleType.TIMER, "resume"),
    IntentType.CANCEL_TIMER: (ScheduleType.TIMER, "cancel"),
}
_HANDLED = frozenset({*_CREATE, *_LIST, *_SHOW, *_UPDATE, *_MUTATE})
_WEEKDAYS = {
    "monday": 0,
    "tuesday": 1,
    "wednesday": 2,
    "thursday": 3,
    "friday": 4,
    "saturday": 5,
    "sunday": 6,
}


@dataclass(frozen=True)
class SchedulingDispatchResult:
    command: UserCommand
    action: Action
    result: ActionResult

    @property
    def user_message(self) -> str:
        return self.result.user_message

    @classmethod
    def from_gateway(cls, value: GatewayDispatchResult) -> SchedulingDispatchResult:
        return cls(value.command, value.action, value.result)


class SchedulingActionDispatcher:
    """Translate one existing parse result into one gateway-submitted action."""

    def __init__(
        self,
        service: SchedulingService,
        gateway: SafeExecutionGateway,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self.service = service
        self.gateway = gateway
        self.clock = clock

    def dispatch(self, parsed: CommandParseResult) -> SchedulingDispatchResult | None:
        command = parsed.command
        if (
            not parsed.matched
            or parsed.requires_clarification
            or command.intent not in _HANDLED
        ):
            return None
        target = self._resolve_target(command)
        parameters = self._parameters(command, target)
        action = Action(
            command_id=command.command_id,
            intent=command.intent,
            parameters=parameters,
            risk_level=self._risk(command.intent),
            permission_decision=PermissionDecision.ALLOW,
            confirmation_status=ConfirmationStatus.NOT_REQUIRED,
            requires_confirmation=False,
        )
        context = SafetyContext(
            command,
            action,
            command.session_id or UUID(int=0),
            logical_source=command.intent.value,
            target_type="local_schedule",
            target_exists=target is not None,
            additional_context={
                "scheduled_command": False,
                "schedule_id": str(target.schedule_id) if target else None,
                "revision": target.revision if target else None,
            },
        )
        fingerprint = self._fingerprint(target)
        result = self.gateway.submit(
            context,
            lambda: self._execute(command, action, target),
            revalidator=lambda: self._current_fingerprint(target),
            fingerprint=fingerprint,
        )
        return SchedulingDispatchResult.from_gateway(result)

    def _execute(
        self,
        command: UserCommand,
        action: Action,
        target: ScheduledItem | None,
    ) -> ActionResult:
        try:
            return self._execute_validated(command, action, target)
        except Exception as error:
            return self.service.failure_result(
                action.action_id,
                command.command_id,
                error,
            )

    def _execute_validated(
        self,
        command: UserCommand,
        action: Action,
        target: ScheduledItem | None,
    ) -> ActionResult:
        intent = command.intent
        if intent in _LIST:
            return self.service.list_items(action.action_id, _LIST[intent])
        if intent in _CREATE:
            now = self._now()
            duration = self._number(command, "duration_seconds")
            due = self._due(command.original_text, now, duration)
            kind = _CREATE[intent]
            title = self._create_title(command.original_text, kind)
            message = self._text(command, "message") or title
            recurrence = (
                self._recurrence(command.original_text)
                if intent
                in {
                    IntentType.CREATE_RECURRING_REMINDER,
                    IntentType.CREATE_RECURRING_ALARM,
                }
                else None
            )
            return self.service.create(
                action.action_id,
                command.command_id,
                kind,
                title,
                message,
                due,
                duration if kind is ScheduleType.TIMER else None,
                recurrence,
                self.service.configuration.timezone,
            )
        if target is None:
            raise ValueError("Specify one existing scheduled item.")
        if intent in _SHOW:
            return self.service.show(
                action.action_id,
                command.command_id,
                target.schedule_id,
            )
        if intent in _UPDATE:
            due = self._due(
                command.original_text,
                self._now(),
                self._number(command, "duration_seconds"),
            )
            return self.service.update(
                action.action_id,
                command.command_id,
                target.schedule_id,
                target.revision,
                due=due,
            )
        _kind, operation = _MUTATE[intent]
        duration = self._number(command, "duration_seconds")
        return self.service.mutate(
            action.action_id,
            command.command_id,
            target.schedule_id,
            operation,
            duration // 60 if duration else None,
            expected_revision=target.revision,
        )

    def _resolve_target(self, command: UserCommand) -> ScheduledItem | None:
        kind = (
            _SHOW.get(command.intent)
            or _UPDATE.get(command.intent)
            or (_MUTATE[command.intent][0] if command.intent in _MUTATE else None)
        )
        if kind is None:
            return None
        try:
            return self.service.resolve_reference(
                kind,
                self._text(command, "title"),
            )
        except ValueError:
            return None

    def _due(
        self,
        text: str,
        now_utc: datetime,
        duration_seconds: int | None,
    ) -> datetime:
        if duration_seconds is not None:
            if duration_seconds < 1:
                raise ValueError("Duration must be positive.")
            return now_utc + timedelta(seconds=duration_seconds)
        clock = re.search(
            r"\b(\d{1,2})(?::(\d{2}))?\s*(am|pm)\b",
            text,
            re.IGNORECASE,
        )
        if not clock:
            raise ValueError("A clear future time is required.")
        hour = int(clock.group(1))
        minute = int(clock.group(2) or 0)
        if not 1 <= hour <= 12 or not 0 <= minute <= 59:
            raise ValueError("The requested clock time is invalid.")
        hour = hour % 12 + (12 if clock.group(3).casefold() == "pm" else 0)
        zone = configured_timezone(self.service.configuration.timezone)
        local_now = now_utc.astimezone(zone)
        selected_date = self._selected_date(text, local_now.date())
        wall = datetime.combine(selected_date, time(hour, minute))
        due = local_datetime_to_utc(wall, zone)
        recurrence_day = self._weekday(text)
        if recurrence_day is not None:
            while due <= now_utc or due.astimezone(zone).weekday() != recurrence_day:
                wall += timedelta(days=1)
                due = local_datetime_to_utc(wall, zone)
        elif due <= now_utc:
            if "tomorrow" in text.casefold():
                raise ValueError("The requested time is already in the past.")
            due = local_datetime_to_utc(wall + timedelta(days=1), zone)
        return due

    @staticmethod
    def _selected_date(text: str, today: date) -> date:
        lowered = text.casefold()
        if "tomorrow" in lowered:
            return today + timedelta(days=1)
        explicit = re.search(r"\b(\d{4})-(\d{2})-(\d{2})\b", text)
        if explicit:
            try:
                return date(*(int(value) for value in explicit.groups()))
            except ValueError as error:
                raise ValueError("The requested date is invalid.") from error
        return today

    def _recurrence(self, text: str) -> RecurrenceRule:
        lowered = text.casefold()
        maximum = self.service.configuration.maximum_recurring_occurrences
        weekday = self._weekday(lowered)
        if "every weekday" in lowered:
            return RecurrenceRule(
                RecurrenceFrequency.WEEKDAYS,
                weekdays=(0, 1, 2, 3, 4),
                maximum_occurrences=maximum,
            )
        if weekday is not None:
            return RecurrenceRule(
                RecurrenceFrequency.WEEKDAYS,
                weekdays=(weekday,),
                maximum_occurrences=maximum,
            )
        interval = re.search(
            r"\bevery\s+(\d+)\s+(minutes?|hours?|days?|weeks?|months?)\b",
            lowered,
        )
        if interval:
            amount = int(interval.group(1))
            unit = interval.group(2)
            if unit.startswith("minute"):
                return RecurrenceRule(
                    RecurrenceFrequency.INTERVAL,
                    interval=amount,
                    maximum_occurrences=maximum,
                )
            if unit.startswith("hour"):
                return RecurrenceRule(
                    RecurrenceFrequency.INTERVAL,
                    interval=amount * 60,
                    maximum_occurrences=maximum,
                )
            frequency = (
                RecurrenceFrequency.DAILY
                if unit.startswith("day")
                else (
                    RecurrenceFrequency.WEEKLY
                    if unit.startswith("week")
                    else RecurrenceFrequency.MONTHLY
                )
            )
            return RecurrenceRule(
                frequency,
                interval=amount,
                maximum_occurrences=maximum,
            )
        frequency = (
            RecurrenceFrequency.MONTHLY
            if "every month" in lowered
            else (
                RecurrenceFrequency.WEEKLY
                if "every week" in lowered
                else RecurrenceFrequency.DAILY
            )
        )
        return RecurrenceRule(frequency, maximum_occurrences=maximum)

    @staticmethod
    def _weekday(text: str) -> int | None:
        lowered = text.casefold()
        return next(
            (value for name, value in _WEEKDAYS.items() if name in lowered),
            None,
        )

    @staticmethod
    def _create_title(text: str, kind: ScheduleType) -> str:
        if kind is ScheduleType.TIMER:
            match = re.match(
                r"^start (?:a |the )?(.+?)?timer for",
                text,
                re.IGNORECASE,
            )
            return match.group(1).strip() if match and match.group(1) else "timer"
        return kind.value

    @staticmethod
    def _risk(intent: IntentType) -> RiskLevel:
        return (
            RiskLevel.LOW
            if intent in {*_CREATE, *_LIST, *_SHOW}
            and intent
            not in {
                IntentType.CREATE_RECURRING_REMINDER,
                IntentType.CREATE_RECURRING_ALARM,
            }
            else RiskLevel.MEDIUM
        )

    @staticmethod
    def _parameters(
        command: UserCommand,
        target: ScheduledItem | None,
    ) -> dict[str, JsonValue]:
        parameters: dict[str, JsonValue] = {
            "scheduled_command": False,
            "source": command.source.value,
        }
        if target:
            parameters.update(
                {
                    "schedule_id": str(target.schedule_id),
                    "schedule_type": target.schedule_type.value,
                    "revision": target.revision,
                }
            )
        return parameters

    @staticmethod
    def _fingerprint(target: ScheduledItem | None) -> ResourceFingerprint | None:
        if target is None:
            return None
        return ResourceFingerprint(
            "schedule",
            str(target.schedule_id),
            True,
            modified_ns=target.revision,
        )

    def _current_fingerprint(
        self,
        target: ScheduledItem | None,
    ) -> ResourceFingerprint | None:
        if target is None:
            return None
        current = self.service.repository.get(target.schedule_id)
        return self._fingerprint(current)

    def _now(self) -> datetime:
        value = self.clock()
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("Scheduling clock must be timezone-aware.")
        return value.astimezone(UTC)

    @staticmethod
    def _text(command: UserCommand, name: str) -> str | None:
        values = [
            entity.value
            for entity in command.entities
            if entity.name == name and isinstance(entity.value, str)
        ]
        return values[0] if len(values) == 1 else None

    @staticmethod
    def _number(command: UserCommand, name: str) -> int | None:
        values = [
            entity.value
            for entity in command.entities
            if entity.name == name
            and isinstance(entity.value, int)
            and not isinstance(entity.value, bool)
        ]
        return values[0] if len(values) == 1 else None
