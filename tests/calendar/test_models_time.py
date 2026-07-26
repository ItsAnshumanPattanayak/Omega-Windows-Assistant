from datetime import UTC, datetime, timedelta

import pytest

from omega.calendar import (
    CalendarConfiguration,
    CalendarConfigurationError,
    CalendarEvent,
    CalendarReminder,
    CalendarValidationError,
    EventVisibility,
    RecurrenceFrequency,
    RecurrenceRule,
)
from omega.calendar.agenda import format_event
from omega.calendar.time_utils import day_range, event_times, parse_clock, week_range


@pytest.mark.parametrize("value", ["4 pm", "4:30 AM", "12 pm", "12 am"])
def test_twelve_hour_clock_is_explicit(value: str) -> None:
    assert parse_clock(value).minute in range(60)


@pytest.mark.parametrize("value", ["4", "13 pm", "25:00", "noonish"])
def test_ambiguous_or_invalid_clock_is_rejected(value: str) -> None:
    with pytest.raises(CalendarValidationError):
        parse_clock(value)


def test_day_and_week_ranges_are_aware_and_deterministic(now: datetime) -> None:
    today = day_range("today", now, "Asia/Calcutta")
    tomorrow = day_range("tomorrow", now, "Asia/Calcutta")
    week = week_range(now, "Asia/Calcutta")
    assert today[0].tzinfo is UTC and tomorrow[0] - today[0] == timedelta(days=1)
    assert week[1] - week[0] == timedelta(days=7)


def test_event_times_convert_local_wall_time_to_utc(now: datetime) -> None:
    start, end = event_times("tomorrow", "4pm", 30, now, "Asia/Calcutta")
    assert start.tzinfo is UTC and end - start == timedelta(minutes=30)


def test_event_requires_aware_ordered_times() -> None:
    with pytest.raises(CalendarValidationError):
        CalendarEvent("primary", "Bad", datetime(2026, 1, 1), datetime(2026, 1, 2))
    start = datetime(2026, 1, 2, tzinfo=UTC)
    with pytest.raises(CalendarValidationError):
        CalendarEvent("primary", "Bad", start, start)


def test_all_day_requires_local_midnight() -> None:
    with pytest.raises(CalendarValidationError):
        CalendarEvent(
            "primary",
            "Bad",
            datetime(2026, 1, 1, 1, tzinfo=UTC),
            datetime(2026, 1, 2, 1, tzinfo=UTC),
            all_day=True,
        )


def test_event_serialization_contains_no_provider_objects(
    events: tuple[CalendarEvent, ...],
) -> None:
    value = events[0].to_dict()
    assert value["event_id"] == "event-1" and isinstance(value["start_at"], str)


def test_private_event_summary_minimizes_content(now: datetime) -> None:
    event = CalendarEvent(
        "primary",
        "Sensitive acquisition",
        now,
        now + timedelta(hours=1),
        location="Secret room",
        visibility=EventVisibility.PRIVATE,
    )
    summary = format_event(event, "UTC")
    assert "Private event" in summary
    assert "Sensitive" not in summary and "Secret room" not in summary


def test_recurrence_is_bounded_and_weekly_requires_days(now: datetime) -> None:
    with pytest.raises(CalendarValidationError):
        RecurrenceRule(RecurrenceFrequency.DAILY)
    with pytest.raises(CalendarValidationError):
        RecurrenceRule(RecurrenceFrequency.WEEKLY, count=2)
    with pytest.raises(CalendarValidationError):
        RecurrenceRule(RecurrenceFrequency.DAILY, count=501)
    assert (
        RecurrenceRule(
            RecurrenceFrequency.WEEKLY, weekdays=(0,), until=now + timedelta(days=30)
        ).to_dict()["frequency"]
        == "weekly"
    )


def test_reminder_and_configuration_limits() -> None:
    with pytest.raises(CalendarValidationError):
        CalendarReminder(-1)
    with pytest.raises(CalendarConfigurationError):
        CalendarConfiguration(require_confirmation_for_delete=False)
    with pytest.raises(CalendarConfigurationError):
        CalendarConfiguration(timezone_name="Not/AZone")
    assert not CalendarConfiguration().enabled
