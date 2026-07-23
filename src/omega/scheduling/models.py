"""Typed scheduling records stored as JSON-compatible SQLite data."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import cast
from uuid import UUID, uuid4

from omega.core.exceptions import ModelValidationError
from omega.models._serialization import JsonValue, validate_json_mapping


class ScheduleType(StrEnum):
    REMINDER = "reminder"
    ALARM = "alarm"
    TIMER = "timer"


class ScheduleStatus(StrEnum):
    PENDING = "pending"
    PAUSED = "paused"
    SNOOZED = "snoozed"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    MISSED = "missed"


class RecurrenceFrequency(StrEnum):
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    WEEKDAYS = "weekdays"
    INTERVAL = "interval"


class DeliveryStatus(StrEnum):
    CLAIMED = "claimed"
    DELIVERED = "delivered"
    FAILED = "failed"
    MISSED = "missed"


def _utc(value: datetime, name: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ModelValidationError(f"{name} must be timezone-aware.")
    return value.astimezone(UTC)


@dataclass(frozen=True)
class RecurrenceRule:
    frequency: RecurrenceFrequency
    interval: int = 1
    weekdays: tuple[int, ...] = ()
    maximum_occurrences: int = 1000
    end_at_utc: datetime | None = None

    def __post_init__(self) -> None:
        if isinstance(self.interval, bool) or self.interval < 1:
            raise ModelValidationError("recurrence interval must be positive.")
        if not 1 <= self.maximum_occurrences <= 10000:
            raise ModelValidationError("maximum_occurrences is outside its safe range.")
        if any(day not in range(7) for day in self.weekdays) or len(
            set(self.weekdays)
        ) != len(self.weekdays):
            raise ModelValidationError(
                "weekdays must be unique values from 0 through 6."
            )
        if self.frequency is RecurrenceFrequency.WEEKDAYS and not self.weekdays:
            raise ModelValidationError("weekday recurrence requires weekdays.")
        if self.end_at_utc is not None:
            object.__setattr__(self, "end_at_utc", _utc(self.end_at_utc, "end_at_utc"))

    def to_dict(self) -> dict[str, JsonValue]:
        return {
            "frequency": self.frequency.value,
            "interval": self.interval,
            "weekdays": list(self.weekdays),
            "maximum_occurrences": self.maximum_occurrences,
            "end_at_utc": self.end_at_utc.isoformat() if self.end_at_utc else None,
        }

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> RecurrenceRule:
        end = data.get("end_at_utc")
        interval = cast(int, data.get("interval", 1))
        weekdays = cast(list[int], data.get("weekdays", []))
        maximum = cast(int, data.get("maximum_occurrences", 1000))
        return cls(
            RecurrenceFrequency(str(data["frequency"])),
            interval,
            tuple(weekdays),
            maximum,
            datetime.fromisoformat(str(end)) if end else None,
        )


@dataclass
class ScheduledItem:
    schedule_type: ScheduleType
    title: str
    message: str
    due_at_utc: datetime
    timezone_name: str
    schedule_id: UUID = field(default_factory=uuid4)
    status: ScheduleStatus = ScheduleStatus.PENDING
    recurrence: RecurrenceRule | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    completed_at: datetime | None = None
    cancelled_at: datetime | None = None
    snoozed_until_utc: datetime | None = None
    remaining_seconds: int | None = None
    occurrence_count: int = 0
    revision: int = 1
    metadata: dict[str, JsonValue] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.title.strip() or len(self.title) > 500 or len(self.message) > 10000:
            raise ModelValidationError("Schedule text is empty or too long.")
        if not self.timezone_name.strip() or len(self.timezone_name) > 100:
            raise ModelValidationError("timezone_name is invalid.")
        self.due_at_utc = _utc(self.due_at_utc, "due_at_utc")
        self.created_at = _utc(self.created_at, "created_at")
        self.updated_at = _utc(self.updated_at, "updated_at")
        for name in ("completed_at", "cancelled_at", "snoozed_until_utc"):
            value = getattr(self, name)
            if value is not None:
                setattr(self, name, _utc(value, name))
        if self.status is ScheduleStatus.PAUSED and (
            self.schedule_type is not ScheduleType.TIMER
            or self.remaining_seconds is None
            or self.remaining_seconds < 1
        ):
            raise ModelValidationError("Paused timers require remaining_seconds.")
        if self.remaining_seconds is not None and (
            isinstance(self.remaining_seconds, bool) or self.remaining_seconds < 1
        ):
            raise ModelValidationError("remaining_seconds must be positive.")
        if self.status is ScheduleStatus.SNOOZED and self.snoozed_until_utc is None:
            raise ModelValidationError("Snoozed items require snoozed_until_utc.")
        if self.snoozed_until_utc is not None and (
            self.status is not ScheduleStatus.SNOOZED
            or self.snoozed_until_utc != self.due_at_utc
        ):
            raise ModelValidationError("Snooze state is inconsistent.")
        if self.completed_at and self.cancelled_at:
            raise ModelValidationError("An item cannot be completed and cancelled.")
        if self.status in {ScheduleStatus.COMPLETED, ScheduleStatus.MISSED}:
            if self.completed_at is None:
                raise ModelValidationError("Completed items require completed_at.")
        elif self.completed_at is not None:
            raise ModelValidationError("Only completed items may have completed_at.")
        if self.status is ScheduleStatus.CANCELLED:
            if self.cancelled_at is None:
                raise ModelValidationError("Cancelled items require cancelled_at.")
        elif self.cancelled_at is not None:
            raise ModelValidationError("Only cancelled items may have cancelled_at.")
        if self.recurrence is not None and self.schedule_type is ScheduleType.TIMER:
            raise ModelValidationError("Timers cannot recur.")
        if self.revision < 1 or self.occurrence_count < 0:
            raise ModelValidationError("Schedule counters are invalid.")
        self.metadata = validate_json_mapping(self.metadata, "metadata")


@dataclass(frozen=True)
class ClaimedOccurrence:
    """One atomically claimed schedule occurrence."""

    delivery_id: UUID
    item: ScheduledItem
    occurrence_at_utc: datetime

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "occurrence_at_utc",
            _utc(self.occurrence_at_utc, "occurrence_at_utc"),
        )
