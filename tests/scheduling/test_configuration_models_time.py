from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from omega.core.exceptions import ConfigurationError, ModelValidationError
from omega.scheduling import (
    RecurrenceFrequency,
    RecurrenceRule,
    ScheduledItem,
    ScheduleStatus,
    ScheduleType,
    SchedulingConfiguration,
    local_datetime_to_utc,
)
from omega.scheduling.recurrence import next_occurrence


def test_configuration_validates_claim_and_batch_bounds() -> None:
    value = SchedulingConfiguration.from_mapping(
        {"claim_timeout_seconds": 30, "maximum_delivery_batch": 200}
    )
    assert value.claim_timeout_seconds == 30
    assert value.maximum_delivery_batch == 200
    for invalid in (
        {"claim_timeout_seconds": 0},
        {"maximum_delivery_batch": True},
        {"unknown": 1},
        {"allow_recurring_scheduled_commands": True},
    ):
        with pytest.raises(ConfigurationError):
            SchedulingConfiguration.from_mapping(invalid)


def test_schedule_lifecycle_invariants_are_strict() -> None:
    now = datetime(2026, 1, 1, tzinfo=UTC)
    with pytest.raises(ModelValidationError):
        ScheduledItem(
            ScheduleType.TIMER,
            "timer",
            "timer",
            now,
            "UTC",
            status=ScheduleStatus.PAUSED,
        )
    with pytest.raises(ModelValidationError):
        ScheduledItem(
            ScheduleType.REMINDER,
            "done",
            "done",
            now,
            "UTC",
            status=ScheduleStatus.COMPLETED,
        )
    with pytest.raises(ModelValidationError):
        ScheduledItem(
            ScheduleType.TIMER,
            "repeat",
            "repeat",
            now,
            "UTC",
            recurrence=RecurrenceRule(RecurrenceFrequency.DAILY),
        )


def test_dst_gap_and_fold_are_rejected_for_direct_input() -> None:
    zone = ZoneInfo("America/New_York")
    with pytest.raises(ModelValidationError, match="does not exist"):
        local_datetime_to_utc(datetime(2026, 3, 8, 2, 30), zone)
    with pytest.raises(ModelValidationError, match="ambiguous"):
        local_datetime_to_utc(datetime(2026, 11, 1, 1, 30), zone)


def test_daily_recurrence_preserves_wall_time_and_skips_dst_gap() -> None:
    current = datetime(2026, 3, 7, 7, 30, tzinfo=UTC)
    result = next_occurrence(
        current,
        RecurrenceRule(RecurrenceFrequency.DAILY),
        "America/New_York",
    )
    assert result == datetime(2026, 3, 9, 6, 30, tzinfo=UTC)


def test_recurrence_is_bounded_by_end_and_occurrence_count() -> None:
    now = datetime(2026, 1, 1, tzinfo=UTC)
    rule = RecurrenceRule(
        RecurrenceFrequency.DAILY,
        maximum_occurrences=2,
        end_at_utc=now + timedelta(days=1),
    )
    assert next_occurrence(now, rule) == now + timedelta(days=1)
    assert next_occurrence(now + timedelta(days=1), rule) is None
