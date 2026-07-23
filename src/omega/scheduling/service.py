"""Validated reminder, alarm, and timer lifecycle operations."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from uuid import UUID

from omega.core.exceptions import DatabaseError, ModelValidationError
from omega.models import ActionResult, ErrorCategory, OmegaErrorDetails
from omega.models._serialization import JsonValue
from omega.scheduling.configuration import SchedulingConfiguration
from omega.scheduling.models import (
    RecurrenceRule,
    ScheduledItem,
    ScheduleStatus,
    ScheduleType,
)
from omega.scheduling.repository import ScheduleRepository


class SchedulingService:
    """Coordinate validated local schedule records without executing commands."""

    def __init__(
        self,
        configuration: SchedulingConfiguration,
        repository: ScheduleRepository,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self.configuration = configuration
        self.repository = repository
        self.clock = clock

    def create(
        self,
        action_id: UUID,
        command_id: UUID,
        kind: ScheduleType,
        title: str,
        message: str,
        due: datetime,
        duration_seconds: int | None = None,
        recurrence: RecurrenceRule | None = None,
        timezone_name: str = "UTC",
    ) -> ActionResult:
        try:
            self._ensure_enabled()
            now = self._now()
            due_utc = self._aware(due, "scheduled time")
            if due_utc <= now:
                raise ValueError("The scheduled time must be in the future.")
            if due_utc - now > timedelta(
                days=self.configuration.maximum_alarm_horizon_days
            ):
                raise ValueError("The scheduled time exceeds the safe horizon.")
            self._validate_text(title, message)
            if (
                self.repository.active_count()
                >= self.configuration.maximum_active_items
            ):
                raise ValueError("The active schedule limit has been reached.")
            if kind is ScheduleType.TIMER:
                if (
                    duration_seconds is None
                    or isinstance(duration_seconds, bool)
                    or not 1
                    <= duration_seconds
                    <= self.configuration.maximum_timer_duration_seconds
                ):
                    raise ValueError("Timer duration is outside the safe range.")
                if recurrence is not None:
                    raise ValueError("Timers cannot recur.")
            if recurrence is not None and (
                recurrence.maximum_occurrences
                > self.configuration.maximum_recurring_occurrences
            ):
                raise ValueError("Recurrence exceeds the configured safe bound.")
            metadata: dict[str, JsonValue] = {}
            if duration_seconds is not None:
                metadata["duration_seconds"] = duration_seconds
            item = ScheduledItem(
                kind,
                title,
                message,
                due_utc,
                timezone_name,
                recurrence=recurrence,
                created_at=now,
                updated_at=now,
                metadata=metadata,
            )
            self.repository.add(item)
            return ActionResult.success_result(
                action_id,
                "Schedule created.",
                f"Scheduled {kind.value} {item.schedule_id} for "
                f"{due_utc.astimezone().strftime('%Y-%m-%d %H:%M')}.",
                data=self._item_data(item),
            )
        except Exception as error:
            return self._failure(action_id, command_id, error)

    def list_items(
        self,
        action_id: UUID,
        kind: ScheduleType | None = None,
        *,
        include_terminal: bool = False,
    ) -> ActionResult:
        try:
            items = self.repository.list_items(
                schedule_type=kind,
                include_terminal=include_terminal,
            )
            data: dict[str, JsonValue] = {
                "items": [self._item_data(item) for item in items]
            }
            label = kind.value + "s" if kind else "scheduled items"
            return ActionResult.success_result(
                action_id,
                "Schedules listed.",
                f"{len(items)} {label}.",
                data=data,
            )
        except Exception as error:
            return self._failure(action_id, UUID(int=0), error)

    def show(
        self,
        action_id: UUID,
        command_id: UUID,
        schedule_id: UUID,
    ) -> ActionResult:
        try:
            item = self.repository.get(schedule_id)
            if item is None:
                raise ValueError("That scheduled item was not found.")
            return ActionResult.success_result(
                action_id,
                "Schedule found.",
                f"{item.schedule_type.value.title()} “{item.title}” is "
                f"{item.status.value} for "
                f"{item.due_at_utc.astimezone().strftime('%Y-%m-%d %H:%M')}.",
                data=self._item_data(item),
            )
        except Exception as error:
            return self._failure(action_id, command_id, error)

    def resolve_reference(
        self,
        kind: ScheduleType,
        title: str | None,
    ) -> ScheduledItem:
        candidates = self.repository.list_items(schedule_type=kind)
        if title:
            candidates = tuple(
                item
                for item in candidates
                if item.title.casefold() == title.strip().casefold()
            )
        if not candidates:
            raise ValueError(f"No active {kind.value} matched that request.")
        if len(candidates) != 1:
            raise ValueError(
                f"More than one {kind.value} matches; specify its exact title."
            )
        return candidates[0]

    def update(
        self,
        action_id: UUID,
        command_id: UUID,
        schedule_id: UUID,
        expected_revision: int,
        *,
        due: datetime | None = None,
        title: str | None = None,
        message: str | None = None,
    ) -> ActionResult:
        try:
            item = self.repository.get(schedule_id)
            if item is None:
                raise ValueError("That scheduled item was not found.")
            if item.revision != expected_revision:
                raise DatabaseError("Schedule revision conflict.")
            if item.status not in _MUTABLE_STATUSES:
                raise ValueError("That scheduled item can no longer be edited.")
            new_title = title if title is not None else item.title
            new_message = message if message is not None else item.message
            self._validate_text(new_title, new_message)
            if due is not None:
                due_utc = self._aware(due, "scheduled time")
                if due_utc <= self._now():
                    raise ValueError("The scheduled time must be in the future.")
                item.due_at_utc = due_utc
            item.title = new_title
            item.message = new_message
            item.snoozed_until_utc = None
            if item.status is ScheduleStatus.SNOOZED:
                item.status = ScheduleStatus.PENDING
            item.updated_at = self._now()
            item.revision += 1
            self.repository.update(item, expected_revision)
            return ActionResult.success_result(
                action_id,
                "Schedule updated.",
                f"Updated {item.schedule_type.value} “{item.title}”.",
                data=self._item_data(item),
            )
        except Exception as error:
            return self._failure(action_id, command_id, error)

    def mutate(
        self,
        action_id: UUID,
        command_id: UUID,
        schedule_id: UUID,
        operation: str,
        minutes: int | None = None,
        *,
        expected_revision: int | None = None,
    ) -> ActionResult:
        try:
            item = self.repository.get(schedule_id)
            if item is None:
                raise ValueError("That scheduled item was not found.")
            if expected_revision is not None and item.revision != expected_revision:
                raise DatabaseError("Schedule revision conflict.")
            old_revision = item.revision
            now = self._now()
            if operation == "cancel" and item.status in _MUTABLE_STATUSES:
                item.status = ScheduleStatus.CANCELLED
                item.cancelled_at = now
                item.snoozed_until_utc = None
                item.remaining_seconds = None
            elif operation in {"complete", "dismiss"} and (
                item.status in _MUTABLE_STATUSES
                and item.schedule_type is not ScheduleType.TIMER
            ):
                item.status = ScheduleStatus.COMPLETED
                item.completed_at = now
                item.snoozed_until_utc = None
                item.remaining_seconds = None
            elif (
                operation == "pause"
                and item.schedule_type is ScheduleType.TIMER
                and item.status is ScheduleStatus.PENDING
            ):
                remaining = int((item.due_at_utc - now).total_seconds())
                if remaining < 1:
                    raise ValueError("That timer has already expired.")
                item.remaining_seconds = remaining
                item.status = ScheduleStatus.PAUSED
            elif (
                operation == "resume"
                and item.schedule_type is ScheduleType.TIMER
                and item.status is ScheduleStatus.PAUSED
            ):
                item.due_at_utc = now + timedelta(seconds=item.remaining_seconds or 1)
                item.remaining_seconds = None
                item.status = ScheduleStatus.PENDING
            elif (
                operation == "snooze"
                and item.schedule_type in {ScheduleType.REMINDER, ScheduleType.ALARM}
                and item.status in {ScheduleStatus.PENDING, ScheduleStatus.SNOOZED}
            ):
                selected = minutes or self.configuration.default_snooze_minutes
                if not 1 <= selected <= self.configuration.maximum_snooze_minutes:
                    raise ValueError("Snooze duration is outside the safe range.")
                item.due_at_utc = now + timedelta(minutes=selected)
                item.snoozed_until_utc = item.due_at_utc
                item.status = ScheduleStatus.SNOOZED
            else:
                raise ValueError("That schedule transition is not valid.")
            item.updated_at = now
            item.revision += 1
            self.repository.update(item, old_revision)
            past = {
                "cancel": "cancelled",
                "complete": "completed",
                "dismiss": "dismissed",
                "pause": "paused",
                "resume": "resumed",
                "snooze": "snoozed",
            }[operation]
            return ActionResult.success_result(
                action_id,
                "Schedule updated.",
                f"The scheduled item was {past}.",
                data=self._item_data(item),
            )
        except Exception as error:
            return self._failure(action_id, command_id, error)

    def _validate_text(self, title: str, message: str) -> None:
        if not title.strip():
            raise ValueError("Schedule title must not be empty.")
        if len(title) > self.configuration.maximum_title_characters:
            raise ValueError("Schedule title is too long.")
        if len(message) > self.configuration.maximum_message_characters:
            raise ValueError("Schedule message is too long.")

    def failure_result(
        self,
        action_id: UUID,
        command_id: UUID,
        error: Exception,
    ) -> ActionResult:
        """Convert a dispatcher validation failure into structured result data."""

        return self._failure(action_id, command_id, error)

    def _ensure_enabled(self) -> None:
        if not self.configuration.enabled:
            raise ValueError("Scheduling is disabled.")

    def _now(self) -> datetime:
        return self._aware(self.clock(), "clock")

    @staticmethod
    def _aware(value: datetime, name: str) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ModelValidationError(f"{name} must be timezone-aware.")
        return value.astimezone(UTC)

    @staticmethod
    def _item_data(item: ScheduledItem) -> dict[str, JsonValue]:
        return {
            "schedule_id": str(item.schedule_id),
            "schedule_type": item.schedule_type.value,
            "title": item.title,
            "message": item.message,
            "status": item.status.value,
            "due_at_utc": item.due_at_utc.isoformat(),
            "timezone_name": item.timezone_name,
            "occurrence_count": item.occurrence_count,
            "revision": item.revision,
            "recurrence": item.recurrence.to_dict() if item.recurrence else None,
        }

    @staticmethod
    def _failure(action_id: UUID, command_id: UUID, error: Exception) -> ActionResult:
        message = str(error) or "Scheduling failed safely."
        category = (
            ErrorCategory.EXECUTION
            if isinstance(error, DatabaseError)
            else ErrorCategory.VALIDATION
        )
        details = OmegaErrorDetails(
            "SCHEDULING_FAILED",
            category,
            type(error).__name__,
            message,
            True,
            action_id=action_id,
            command_id=command_id,
        )
        return ActionResult.failure_result(
            action_id,
            type(error).__name__,
            message,
            details,
        )


_MUTABLE_STATUSES = {
    ScheduleStatus.PENDING,
    ScheduleStatus.PAUSED,
    ScheduleStatus.SNOOZED,
}
