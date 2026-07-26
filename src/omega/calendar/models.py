"""Provider-independent, JSON-compatible calendar domain models."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from uuid import uuid4
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from omega.calendar.exceptions import CalendarValidationError
from omega.email.models import EmailAddress
from omega.models._serialization import JsonValue, validate_json_mapping


class EventVisibility(StrEnum):
    DEFAULT = "default"
    PUBLIC = "public"
    PRIVATE = "private"
    CONFIDENTIAL = "confidential"


class AvailabilityStatus(StrEnum):
    BUSY = "busy"
    FREE = "free"
    TENTATIVE = "tentative"
    OUT_OF_OFFICE = "out_of_office"


class InvitationResponse(StrEnum):
    NEEDS_ACTION = "needs_action"
    ACCEPTED = "accepted"
    DECLINED = "declined"
    TENTATIVE = "tentative"


class RecurrenceFrequency(StrEnum):
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"


class RecurrenceScope(StrEnum):
    THIS_EVENT = "this_event"
    THIS_AND_FUTURE = "this_and_future"
    ALL_EVENTS = "all_events"


class ReminderMethod(StrEnum):
    DISPLAY = "display"
    EMAIL = "email"


class CalendarOperationStatus(StrEnum):
    PENDING = "pending"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    AMBIGUOUS = "ambiguous"


def utc_now() -> datetime:
    return datetime.now(UTC)


def aware(value: datetime, name: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise CalendarValidationError(f"{name} must be timezone-aware.")
    return value


def clean(
    value: str,
    name: str,
    maximum: int,
    *,
    empty: bool = False,
    multiline: bool = False,
) -> str:
    if (
        "\x00" in value
        or (not multiline and ("\r" in value or "\n" in value))
        or (not empty and not value.strip())
        or len(value) > maximum
    ):
        raise CalendarValidationError(f"{name} is empty or exceeds its safe limit.")
    return value.strip()


@dataclass(frozen=True)
class CalendarReminder:
    minutes_before: int
    method: ReminderMethod = ReminderMethod.DISPLAY

    def __post_init__(self) -> None:
        if (
            isinstance(self.minutes_before, bool)
            or not 0 <= self.minutes_before <= 40_320
        ):
            raise CalendarValidationError(
                "Reminder lead time is outside its safe range."
            )

    def to_dict(self) -> dict[str, JsonValue]:
        return {"minutes_before": self.minutes_before, "method": self.method.value}


@dataclass(frozen=True)
class RecurrenceRule:
    frequency: RecurrenceFrequency
    interval: int = 1
    weekdays: tuple[int, ...] = ()
    count: int | None = None
    until: datetime | None = None

    def __post_init__(self) -> None:
        if isinstance(self.interval, bool) or not 1 <= self.interval <= 365:
            raise CalendarValidationError(
                "Recurrence interval is outside its safe range."
            )
        if any(day not in range(7) for day in self.weekdays) or len(
            set(self.weekdays)
        ) != len(self.weekdays):
            raise CalendarValidationError(
                "Recurrence weekdays must be unique values from 0 through 6."
            )
        if self.frequency is RecurrenceFrequency.WEEKLY and not self.weekdays:
            raise CalendarValidationError(
                "Weekly recurrence requires at least one weekday."
            )
        if self.count is not None and (
            isinstance(self.count, bool) or not 1 <= self.count <= 500
        ):
            raise CalendarValidationError("Recurrence count must be between 1 and 500.")
        if self.count is None and self.until is None:
            raise CalendarValidationError("Recurrence must have a count or end date.")
        if self.until is not None:
            aware(self.until, "recurrence until")

    def to_dict(self) -> dict[str, JsonValue]:
        return {
            "frequency": self.frequency.value,
            "interval": self.interval,
            "weekdays": list(self.weekdays),
            "count": self.count,
            "until": self.until.isoformat() if self.until else None,
        }


@dataclass(frozen=True)
class CalendarEvent:
    calendar_id: str
    title: str
    start_at: datetime
    end_at: datetime
    event_id: str = field(default_factory=lambda: str(uuid4()))
    description: str = ""
    location: str = ""
    all_day: bool = False
    timezone_name: str = "UTC"
    attendees: tuple[EmailAddress, ...] = ()
    organizer: EmailAddress | None = None
    recurrence: RecurrenceRule | None = None
    reminders: tuple[CalendarReminder, ...] = ()
    visibility: EventVisibility = EventVisibility.DEFAULT
    availability: AvailabilityStatus = AvailabilityStatus.BUSY
    invitation_response: InvitationResponse = InvitationResponse.NEEDS_ACTION
    etag: str = "1"
    metadata: dict[str, JsonValue] = field(default_factory=dict)

    def __post_init__(self) -> None:
        clean(self.calendar_id, "calendar_id", 200)
        clean(self.event_id, "event_id", 500)
        clean(self.title, "title", 1_000)
        clean(
            self.description,
            "description",
            100_000,
            empty=True,
            multiline=True,
        )
        clean(self.location, "location", 2_000, empty=True)
        aware(self.start_at, "start_at")
        aware(self.end_at, "end_at")
        if self.end_at <= self.start_at:
            raise CalendarValidationError("Event end must be after its start.")
        try:
            zone = ZoneInfo(self.timezone_name)
        except (ZoneInfoNotFoundError, ValueError) as error:
            raise CalendarValidationError("Event timezone is invalid.") from error
        if self.all_day:
            local_start = self.start_at.astimezone(zone)
            local_end = self.end_at.astimezone(zone)
            if any(
                (
                    local_start.hour,
                    local_start.minute,
                    local_start.second,
                    local_start.microsecond,
                    local_end.hour,
                    local_end.minute,
                    local_end.second,
                    local_end.microsecond,
                )
            ):
                raise CalendarValidationError(
                    "All-day events must use local midnight boundaries."
                )
        if len(self.attendees) > 200 or len(set(self.attendees)) != len(self.attendees):
            raise CalendarValidationError(
                "Attendees are duplicated or exceed the safe limit."
            )
        if len(self.reminders) > 10 or len(set(self.reminders)) != len(self.reminders):
            raise CalendarValidationError(
                "Reminders are duplicated or exceed the safe limit."
            )
        validate_json_mapping(self.metadata, "metadata")

    def to_dict(self) -> dict[str, JsonValue]:
        return {
            "event_id": self.event_id,
            "calendar_id": self.calendar_id,
            "title": self.title,
            "description": self.description,
            "location": self.location,
            "start_at": self.start_at.isoformat(),
            "end_at": self.end_at.isoformat(),
            "all_day": self.all_day,
            "timezone_name": self.timezone_name,
            "attendees": [str(item) for item in self.attendees],
            "organizer": str(self.organizer) if self.organizer else None,
            "recurrence": self.recurrence.to_dict() if self.recurrence else None,
            "reminders": [item.to_dict() for item in self.reminders],
            "visibility": self.visibility.value,
            "availability": self.availability.value,
            "invitation_response": self.invitation_response.value,
            "etag": self.etag,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class EventProposal:
    event: CalendarEvent
    proposal_id: str = field(default_factory=lambda: str(uuid4()))
    created_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        aware(self.created_at, "created_at")


@dataclass(frozen=True)
class EventUpdateRequest:
    event_id: str
    title: str | None = None
    start_at: datetime | None = None
    end_at: datetime | None = None
    location: str | None = None
    description: str | None = None
    scope: RecurrenceScope | None = None

    def __post_init__(self) -> None:
        clean(self.event_id, "event_id", 500)
        if not any(
            (
                self.title is not None,
                self.start_at is not None,
                self.end_at is not None,
                self.location is not None,
                self.description is not None,
            )
        ):
            raise CalendarValidationError(
                "An event update must change at least one field."
            )
        if self.title is not None:
            clean(self.title, "title", 1_000)
        if self.start_at is not None:
            aware(self.start_at, "start_at")
        if self.end_at is not None:
            aware(self.end_at, "end_at")


@dataclass(frozen=True)
class CalendarSearchCriteria:
    start_at: datetime
    end_at: datetime
    text: str | None = None
    limit: int = 50

    def __post_init__(self) -> None:
        aware(self.start_at, "start_at")
        aware(self.end_at, "end_at")
        if self.end_at <= self.start_at:
            raise CalendarValidationError("Calendar search range is invalid.")
        if self.text is not None:
            clean(self.text, "search text", 2_000)
        if isinstance(self.limit, bool) or not 1 <= self.limit <= 200:
            raise CalendarValidationError("Calendar search limit is invalid.")


@dataclass(frozen=True)
class AvailabilityInterval:
    start_at: datetime
    end_at: datetime
    status: AvailabilityStatus = AvailabilityStatus.BUSY

    def __post_init__(self) -> None:
        aware(self.start_at, "start_at")
        aware(self.end_at, "end_at")
        if self.end_at <= self.start_at:
            raise CalendarValidationError("Availability interval is invalid.")


@dataclass(frozen=True)
class CalendarPage:
    items: tuple[CalendarEvent, ...]
    limit: int
    next_page_token: str | None = None


@dataclass(frozen=True)
class CalendarOperationOutcome:
    operation_id: str
    operation_type: str
    target_id: str
    status: CalendarOperationStatus
    provider_reference: str | None = None


@dataclass(frozen=True)
class CalendarProviderCapabilities:
    supports_search: bool = True
    supports_availability: bool = True
    supports_recurrence: bool = True
    supports_reminders: bool = True
    supports_invitation_responses: bool = True
