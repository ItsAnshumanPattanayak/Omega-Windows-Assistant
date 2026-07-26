"""Provider-independent calendar workflows with bounded session selection."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import timedelta
from threading import RLock
from uuid import UUID

from omega.calendar.agenda import summarize_agenda
from omega.calendar.configuration import CalendarConfiguration
from omega.calendar.exceptions import (
    CalendarNotFoundError,
    CalendarProviderTimeout,
    CalendarUnavailableError,
    CalendarValidationError,
)
from omega.calendar.models import (
    AvailabilityInterval,
    AvailabilityStatus,
    CalendarEvent,
    CalendarOperationOutcome,
    CalendarOperationStatus,
    CalendarPage,
    CalendarSearchCriteria,
    EventProposal,
    EventUpdateRequest,
    InvitationResponse,
    RecurrenceScope,
)
from omega.calendar.protocols import CalendarProvider
from omega.calendar.repository import (
    CalendarOperationStore,
    InMemoryCalendarOperationStore,
)


@dataclass
class _Selection:
    event_ids: tuple[str, ...] = ()
    current_event_id: str | None = None
    create_proposal: EventProposal | None = None
    update_proposal: EventUpdateRequest | None = None


class CalendarService:
    def __init__(
        self,
        configuration: CalendarConfiguration,
        provider: CalendarProvider | None = None,
        operation_store: CalendarOperationStore | None = None,
    ) -> None:
        self.configuration = configuration
        self.provider = provider
        self.operation_store = operation_store or InMemoryCalendarOperationStore()
        self._selections: dict[UUID, _Selection] = {}
        self._lock = RLock()

    @property
    def available(self) -> bool:
        return self.configuration.enabled and self.provider is not None

    def status(self) -> str:
        if not self.configuration.enabled:
            return "Calendar assistance is disabled."
        if self.provider is None:
            return "Calendar assistance is enabled but no provider is configured."
        return f"Calendar assistance is connected to account profile {self._account()}."

    def list_events(
        self, session_id: UUID, criteria: CalendarSearchCriteria
    ) -> CalendarPage:
        bounded = replace(
            criteria,
            limit=min(criteria.limit, self.configuration.maximum_events_per_request),
        )
        self._validate_range(bounded)
        page = self._provider().list_events(bounded)
        self._record_page(session_id, page)
        return page

    def search(
        self, session_id: UUID, criteria: CalendarSearchCriteria
    ) -> CalendarPage:
        if (
            criteria.text
            and len(criteria.text) > self.configuration.maximum_search_query_characters
        ):
            raise CalendarValidationError(
                "Calendar search exceeds the configured limit."
            )
        bounded = replace(
            criteria,
            limit=min(criteria.limit, self.configuration.maximum_events_per_request),
        )
        self._validate_range(bounded)
        page = self._provider().search_events(bounded)
        self._record_page(session_id, page)
        return page

    def read_event(
        self, session_id: UUID, reference: int | None = None
    ) -> CalendarEvent:
        event_id = self.resolve_event_id(session_id, reference)
        event = self._provider().read_event(event_id)
        self._selections[session_id].current_event_id = event_id
        return event

    def resolve_event_id(self, session_id: UUID, reference: int | None = None) -> str:
        selection = self._selections.get(session_id)
        if selection is None:
            raise CalendarNotFoundError("List or search calendar events first.")
        if reference is None:
            if selection.current_event_id is None:
                raise CalendarNotFoundError("Open a selected event first.")
            return selection.current_event_id
        if isinstance(reference, bool) or not 1 <= reference <= len(
            selection.event_ids
        ):
            raise CalendarNotFoundError(
                "That event number is not in the current result set."
            )
        return selection.event_ids[reference - 1]

    def availability(
        self, criteria: CalendarSearchCriteria
    ) -> tuple[AvailabilityInterval, ...]:
        self._validate_range(criteria)
        return self._provider().availability(criteria)

    def conflicts(self, event: CalendarEvent) -> tuple[AvailabilityInterval, ...]:
        """Return provider-reported busy intervals overlapping a proposal."""
        return self.availability(
            CalendarSearchCriteria(event.start_at, event.end_at, limit=10)
        )

    def free_intervals(
        self,
        criteria: CalendarSearchCriteria,
        *,
        minimum_minutes: int | None = None,
    ) -> tuple[AvailabilityInterval, ...]:
        """Return bounded gaps after merging overlapping busy intervals."""
        minimum_minutes = (
            self.configuration.minimum_free_slot_minutes
            if minimum_minutes is None
            else minimum_minutes
        )
        if isinstance(minimum_minutes, bool) or not 1 <= minimum_minutes <= 1_440:
            raise CalendarValidationError("Minimum free-slot duration is invalid.")
        busy = sorted(
            self.availability(criteria), key=lambda item: (item.start_at, item.end_at)
        )
        cursor = criteria.start_at
        minimum = timedelta(minutes=minimum_minutes)
        free: list[AvailabilityInterval] = []
        for item in busy:
            start = max(item.start_at, criteria.start_at)
            end = min(item.end_at, criteria.end_at)
            if start - cursor >= minimum:
                free.append(
                    AvailabilityInterval(cursor, start, AvailabilityStatus.FREE)
                )
            cursor = max(cursor, end)
        if criteria.end_at - cursor >= minimum:
            free.append(
                AvailabilityInterval(cursor, criteria.end_at, AvailabilityStatus.FREE)
            )
        return tuple(free)

    def agenda(self, session_id: UUID, criteria: CalendarSearchCriteria) -> str:
        return summarize_agenda(
            self.list_events(session_id, criteria).items,
            self.configuration.timezone_name,
        )

    def propose_create(self, session_id: UUID, event: CalendarEvent) -> EventProposal:
        self._validate_event(event)
        proposal = EventProposal(event)
        self._selections.setdefault(session_id, _Selection()).create_proposal = proposal
        return proposal

    def selected_create_proposal(self, session_id: UUID) -> EventProposal:
        proposal = self._selections.get(session_id, _Selection()).create_proposal
        if proposal is None:
            raise CalendarNotFoundError("Create an event proposal first.")
        return proposal

    def commit_create(
        self, session_id: UUID, operation_id: str
    ) -> CalendarOperationOutcome:
        proposal = self.selected_create_proposal(session_id)
        target = proposal.proposal_id
        self._claim(operation_id, "create", target)
        try:
            event = self._provider().create_event(proposal.event, operation_id)
        except CalendarProviderTimeout:
            self.operation_store.finish(operation_id, CalendarOperationStatus.AMBIGUOUS)
            raise
        except Exception:
            self.operation_store.finish(operation_id, CalendarOperationStatus.FAILED)
            raise
        self.operation_store.finish(
            operation_id, CalendarOperationStatus.SUCCEEDED, event.event_id
        )
        self._selections[session_id].create_proposal = None
        return CalendarOperationOutcome(
            operation_id,
            "create",
            target,
            CalendarOperationStatus.SUCCEEDED,
            event.event_id,
        )

    def propose_update(
        self, session_id: UUID, request: EventUpdateRequest
    ) -> EventUpdateRequest:
        event = self.read_event(session_id)
        recurring = event.recurrence is not None
        if recurring and request.scope is None:
            raise CalendarValidationError(
                "Choose a recurrence scope before changing a recurring event."
            )
        self._selections[session_id].update_proposal = request
        return request

    def commit_update(
        self, session_id: UUID, operation_id: str
    ) -> CalendarOperationOutcome:
        selection = self._selections.get(session_id)
        request = selection.update_proposal if selection else None
        if request is None:
            raise CalendarNotFoundError("Create an event update proposal first.")
        assert selection is not None
        self._claim(
            operation_id,
            "update",
            f"{request.event_id}:{self._provider().read_event(request.event_id).etag}",
        )
        try:
            event = self._provider().update_event(request, operation_id)
        except CalendarProviderTimeout:
            self.operation_store.finish(operation_id, CalendarOperationStatus.AMBIGUOUS)
            raise
        except Exception:
            self.operation_store.finish(operation_id, CalendarOperationStatus.FAILED)
            raise
        self.operation_store.finish(
            operation_id, CalendarOperationStatus.SUCCEEDED, event.event_id
        )
        selection.update_proposal = None
        return CalendarOperationOutcome(
            operation_id,
            "update",
            request.event_id,
            CalendarOperationStatus.SUCCEEDED,
            event.event_id,
        )

    def delete_selected(
        self, session_id: UUID, scope: RecurrenceScope | None, operation_id: str
    ) -> CalendarOperationOutcome:
        event = self.read_event(session_id)
        if event.recurrence is not None and scope is None:
            raise CalendarValidationError(
                "Choose a recurrence scope before deleting a recurring event."
            )
        self._claim(operation_id, "delete", f"{event.event_id}:{event.etag}")
        try:
            reference = self._provider().delete_event(
                event.event_id, scope, operation_id
            )
        except CalendarProviderTimeout:
            self.operation_store.finish(operation_id, CalendarOperationStatus.AMBIGUOUS)
            raise
        except Exception:
            self.operation_store.finish(operation_id, CalendarOperationStatus.FAILED)
            raise
        self.operation_store.finish(
            operation_id, CalendarOperationStatus.SUCCEEDED, reference
        )
        self._selections[session_id].current_event_id = None
        return CalendarOperationOutcome(
            operation_id,
            "delete",
            event.event_id,
            CalendarOperationStatus.SUCCEEDED,
            reference,
        )

    def respond(
        self, session_id: UUID, response: InvitationResponse, operation_id: str
    ) -> CalendarOperationOutcome:
        event = self.read_event(session_id)
        self._claim(operation_id, "respond", f"{event.event_id}:{response.value}")
        try:
            updated = self._provider().respond_to_invitation(
                event.event_id, response, operation_id
            )
        except CalendarProviderTimeout:
            self.operation_store.finish(operation_id, CalendarOperationStatus.AMBIGUOUS)
            raise
        except Exception:
            self.operation_store.finish(operation_id, CalendarOperationStatus.FAILED)
            raise
        self.operation_store.finish(
            operation_id, CalendarOperationStatus.SUCCEEDED, updated.event_id
        )
        return CalendarOperationOutcome(
            operation_id,
            "respond",
            event.event_id,
            CalendarOperationStatus.SUCCEEDED,
            updated.event_id,
        )

    def clear_session(self, session_id: UUID | None) -> None:
        if session_id is not None:
            self._selections.pop(session_id, None)

    def _record_page(self, session_id: UUID, page: CalendarPage) -> None:
        if len(page.items) > self.configuration.maximum_events_per_request:
            raise CalendarValidationError("Provider returned too many events.")
        with self._lock:
            self._selections[session_id] = _Selection(
                tuple(item.event_id for item in page.items)
            )

    def _validate_event(self, event: CalendarEvent) -> None:
        if (
            len(event.title) > self.configuration.maximum_title_characters
            or len(event.description)
            > self.configuration.maximum_description_characters
            or len(event.location) > self.configuration.maximum_location_characters
            or len(event.attendees) > self.configuration.maximum_attendees
        ):
            raise CalendarValidationError("Event exceeds configured content limits.")
        if (
            event.recurrence
            and event.recurrence.count
            and event.recurrence.count
            > self.configuration.maximum_recurrence_occurrences
        ):
            raise CalendarValidationError(
                "Event recurrence exceeds the configured limit."
            )
        duration = event.end_at - event.start_at
        if duration < timedelta(
            minutes=self.configuration.minimum_event_duration_minutes
        ) or duration > timedelta(
            hours=self.configuration.maximum_event_duration_hours
        ):
            raise CalendarValidationError("Event duration exceeds configured limits.")
        if len(event.reminders) > self.configuration.maximum_reminders or any(
            item.minutes_before
            > self.configuration.maximum_reminder_lead_days * 24 * 60
            for item in event.reminders
        ):
            raise CalendarValidationError("Event reminders exceed configured limits.")
        if event.recurrence and event.recurrence.until:
            if event.recurrence.until <= event.start_at:
                raise CalendarValidationError(
                    "Event recurrence must end after the first occurrence."
                )

    def _claim(self, operation_id: str, operation_type: str, target: str) -> None:
        if not self.operation_store.claim(
            operation_id, self._account(), operation_type, target
        ):
            raise CalendarValidationError(
                "This calendar mutation already has an operation receipt and will "
                "not be repeated."
            )

    def _validate_range(self, criteria: CalendarSearchCriteria) -> None:
        if criteria.end_at - criteria.start_at > timedelta(
            days=self.configuration.maximum_date_range_days
        ):
            raise CalendarValidationError(
                "Calendar date range exceeds the configured limit."
            )

    def _provider(self) -> CalendarProvider:
        if not self.configuration.enabled:
            raise CalendarUnavailableError(
                "Calendar assistance is disabled in configuration."
            )
        if self.provider is None:
            raise CalendarUnavailableError("No calendar provider is configured.")
        return self.provider

    def _account(self) -> str:
        return self.configuration.account_name or "default"
