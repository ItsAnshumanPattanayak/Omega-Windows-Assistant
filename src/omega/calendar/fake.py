"""Deterministic zero-network calendar provider for tests and demos."""

from __future__ import annotations

from dataclasses import replace
from threading import RLock

from omega.calendar.exceptions import CalendarNotFoundError, CalendarProviderTimeout
from omega.calendar.models import (
    AvailabilityInterval,
    AvailabilityStatus,
    CalendarEvent,
    CalendarPage,
    CalendarProviderCapabilities,
    CalendarSearchCriteria,
    EventUpdateRequest,
    InvitationResponse,
    RecurrenceScope,
)


class FakeCalendarProvider:
    def __init__(self, events: tuple[CalendarEvent, ...] = ()) -> None:
        self._events = {item.event_id: item for item in events}
        self._operations: dict[str, object] = {}
        self._lock = RLock()
        self.network_operations = 0
        self.create_count = self.update_count = self.delete_count = (
            self.response_count
        ) = 0
        self.timeout_next_mutation = False

    @property
    def capabilities(self) -> CalendarProviderCapabilities:
        return CalendarProviderCapabilities()

    def list_events(self, criteria: CalendarSearchCriteria) -> CalendarPage:
        items = sorted(
            (
                item
                for item in self._events.values()
                if item.start_at < criteria.end_at and item.end_at > criteria.start_at
            ),
            key=lambda item: (item.start_at, item.event_id),
        )[: criteria.limit]
        return CalendarPage(tuple(items), criteria.limit)

    def search_events(self, criteria: CalendarSearchCriteria) -> CalendarPage:
        page = self.list_events(criteria)
        needle = (criteria.text or "").casefold()
        items = tuple(
            item
            for item in page.items
            if needle in f"{item.title} {item.description} {item.location}".casefold()
        )
        return CalendarPage(items, criteria.limit)

    def read_event(self, event_id: str) -> CalendarEvent:
        try:
            return self._events[event_id]
        except KeyError as error:
            raise CalendarNotFoundError(
                "The selected event is no longer available."
            ) from error

    def availability(
        self, criteria: CalendarSearchCriteria
    ) -> tuple[AvailabilityInterval, ...]:
        return tuple(
            AvailabilityInterval(item.start_at, item.end_at, AvailabilityStatus.BUSY)
            for item in self.list_events(criteria).items
            if item.availability is not AvailabilityStatus.FREE
        )

    def _before_mutation(self, operation_id: str) -> object | None:
        if operation_id in self._operations:
            return self._operations[operation_id]
        if self.timeout_next_mutation:
            self.timeout_next_mutation = False
            raise CalendarProviderTimeout(
                "Calendar provider timeout; mutation outcome is ambiguous."
            )
        return None

    def create_event(self, event: CalendarEvent, operation_id: str) -> CalendarEvent:
        with self._lock:
            prior = self._before_mutation(operation_id)
            if isinstance(prior, CalendarEvent):
                return prior
            self._events[event.event_id] = event
            self._operations[operation_id] = event
            self.create_count += 1
            return event

    def update_event(
        self, request: EventUpdateRequest, operation_id: str
    ) -> CalendarEvent:
        with self._lock:
            prior = self._before_mutation(operation_id)
            if isinstance(prior, CalendarEvent):
                return prior
            event = self.read_event(request.event_id)
            updated = replace(
                event,
                title=request.title or event.title,
                start_at=request.start_at or event.start_at,
                end_at=request.end_at or event.end_at,
                location=(
                    request.location if request.location is not None else event.location
                ),
                description=(
                    request.description
                    if request.description is not None
                    else event.description
                ),
                etag=str(int(event.etag) + 1),
            )
            self._events[event.event_id] = updated
            self._operations[operation_id] = updated
            self.update_count += 1
            return updated

    def delete_event(
        self, event_id: str, scope: RecurrenceScope | None, operation_id: str
    ) -> str:
        del scope
        with self._lock:
            prior = self._before_mutation(operation_id)
            if isinstance(prior, str):
                return prior
            self.read_event(event_id)
            del self._events[event_id]
            reference = f"deleted-{event_id}"
            self._operations[operation_id] = reference
            self.delete_count += 1
            return reference

    def respond_to_invitation(
        self, event_id: str, response: InvitationResponse, operation_id: str
    ) -> CalendarEvent:
        with self._lock:
            prior = self._before_mutation(operation_id)
            if isinstance(prior, CalendarEvent):
                return prior
            event = replace(self.read_event(event_id), invitation_response=response)
            self._events[event_id] = event
            self._operations[operation_id] = event
            self.response_count += 1
            return event
