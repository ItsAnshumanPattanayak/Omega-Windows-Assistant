"""Deterministic calendar date and wall-time interpretation."""

from __future__ import annotations

import re
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from omega.calendar.exceptions import CalendarValidationError
from omega.scheduling.time_utils import local_datetime_to_utc

_WEEKDAYS = {
    name: index
    for index, name in enumerate(
        ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")
    )
}


def day_range(
    reference: str, now: datetime, timezone_name: str
) -> tuple[datetime, datetime]:
    zone = ZoneInfo(timezone_name)
    local = now.astimezone(zone)
    token = reference.casefold().strip()
    if token.startswith("next "):
        token = token[5:]
    if token == "today":
        target = local.date()
    elif token == "tomorrow":
        target = local.date() + timedelta(days=1)
    elif token in _WEEKDAYS:
        delta = (_WEEKDAYS[token] - local.weekday()) % 7 or 7
        target = local.date() + timedelta(days=delta)
    else:
        try:
            target = date.fromisoformat(token)
        except ValueError as error:
            raise CalendarValidationError(
                "Use today, tomorrow, a weekday, or YYYY-MM-DD."
            ) from error
    start = datetime.combine(target, time.min, zone)
    return start.astimezone(UTC), (start + timedelta(days=1)).astimezone(UTC)


def week_range(now: datetime, timezone_name: str) -> tuple[datetime, datetime]:
    zone = ZoneInfo(timezone_name)
    local = now.astimezone(zone)
    start = datetime.combine(local.date(), time.min, zone)
    return start.astimezone(UTC), (start + timedelta(days=7)).astimezone(UTC)


def parse_clock(value: str) -> time:
    token = value.strip().casefold()
    match = re.fullmatch(r"(\d{1,2})(?::(\d{2}))?\s*(am|pm)?", token)
    if not match or match.group(3) is None:
        raise CalendarValidationError("Specify am or pm, or use 24-hour HH:MM time.")
    hour, minute, meridiem = (
        int(match.group(1)),
        int(match.group(2) or 0),
        match.group(3),
    )
    if not 1 <= hour <= 12 or minute > 59:
        raise CalendarValidationError("Clock time is invalid.")
    hour = hour % 12 + (12 if meridiem == "pm" else 0)
    return time(hour, minute)


def parse_24h_clock(value: str) -> time:
    try:
        return time.fromisoformat(value)
    except ValueError as error:
        raise CalendarValidationError("Clock time is invalid.") from error


def event_times(
    day: str, start_text: str, duration_minutes: int, now: datetime, timezone_name: str
) -> tuple[datetime, datetime]:
    if isinstance(duration_minutes, bool) or not 1 <= duration_minutes <= 10_080:
        raise CalendarValidationError(
            "Event duration must be between 1 minute and 7 days."
        )
    start_day, _ = day_range(day, now, timezone_name)
    zone = ZoneInfo(timezone_name)
    clock = (
        parse_24h_clock(start_text)
        if re.fullmatch(r"\d{2}:\d{2}", start_text.strip())
        else parse_clock(start_text)
    )
    wall = datetime.combine(start_day.astimezone(zone).date(), clock)
    start = local_datetime_to_utc(wall, zone)
    return start, start + timedelta(minutes=duration_minutes)
