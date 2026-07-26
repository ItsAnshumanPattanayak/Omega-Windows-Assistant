"""Narrow provider boundary for calendar business logic."""

from typing import Protocol

from omega.calendar.models import (
    AvailabilityInterval,
    CalendarEvent,
    CalendarPage,
    CalendarProviderCapabilities,
    CalendarSearchCriteria,
    EventUpdateRequest,
    InvitationResponse,
    RecurrenceScope,
)


class CalendarProvider(Protocol):
    @property
    def capabilities(self) -> CalendarProviderCapabilities: ...
    def list_events(self, criteria: CalendarSearchCriteria) -> CalendarPage: ...
    def search_events(self, criteria: CalendarSearchCriteria) -> CalendarPage: ...
    def read_event(self, event_id: str) -> CalendarEvent: ...
    def availability(
        self, criteria: CalendarSearchCriteria
    ) -> tuple[AvailabilityInterval, ...]: ...
    def create_event(
        self, event: CalendarEvent, operation_id: str
    ) -> CalendarEvent: ...
    def update_event(
        self, request: EventUpdateRequest, operation_id: str
    ) -> CalendarEvent: ...
    def delete_event(
        self, event_id: str, scope: RecurrenceScope | None, operation_id: str
    ) -> str: ...
    def respond_to_invitation(
        self, event_id: str, response: InvitationResponse, operation_id: str
    ) -> CalendarEvent: ...
