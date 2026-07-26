"""Public privacy-first calendar API."""

from omega.calendar.configuration import CalendarConfiguration
from omega.calendar.exceptions import (
    CalendarConfigurationError,
    CalendarError,
    CalendarNotFoundError,
    CalendarProviderError,
    CalendarProviderTimeout,
    CalendarUnavailableError,
    CalendarValidationError,
)
from omega.calendar.fake import FakeCalendarProvider
from omega.calendar.models import (
    AvailabilityInterval,
    AvailabilityStatus,
    CalendarEvent,
    CalendarOperationOutcome,
    CalendarOperationStatus,
    CalendarPage,
    CalendarProviderCapabilities,
    CalendarReminder,
    CalendarSearchCriteria,
    EventProposal,
    EventUpdateRequest,
    EventVisibility,
    InvitationResponse,
    RecurrenceFrequency,
    RecurrenceRule,
    RecurrenceScope,
    ReminderMethod,
)
from omega.calendar.repository import (
    InMemoryCalendarOperationStore,
    SqliteCalendarOperationStore,
)
from omega.calendar.service import CalendarService

__all__ = [
    "AvailabilityInterval",
    "AvailabilityStatus",
    "CalendarConfiguration",
    "CalendarConfigurationError",
    "CalendarError",
    "CalendarEvent",
    "CalendarNotFoundError",
    "CalendarOperationOutcome",
    "CalendarOperationStatus",
    "CalendarPage",
    "CalendarProviderCapabilities",
    "CalendarProviderError",
    "CalendarProviderTimeout",
    "CalendarReminder",
    "CalendarSearchCriteria",
    "CalendarService",
    "CalendarUnavailableError",
    "CalendarValidationError",
    "EventProposal",
    "EventUpdateRequest",
    "EventVisibility",
    "FakeCalendarProvider",
    "InMemoryCalendarOperationStore",
    "InvitationResponse",
    "RecurrenceFrequency",
    "RecurrenceRule",
    "RecurrenceScope",
    "ReminderMethod",
    "SqliteCalendarOperationStore",
]
