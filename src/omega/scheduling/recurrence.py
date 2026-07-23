"""Bounded next-occurrence calculation; invalid monthly days are skipped."""

from __future__ import annotations

import calendar
from datetime import UTC, datetime, timedelta

from omega.core.exceptions import ModelValidationError
from omega.scheduling.models import RecurrenceFrequency, RecurrenceRule
from omega.scheduling.time_utils import configured_timezone, local_datetime_to_utc


def next_occurrence(
    current_utc: datetime,
    rule: RecurrenceRule,
    timezone_name: str | None = None,
) -> datetime | None:
    if current_utc.tzinfo is None:
        raise ModelValidationError("current occurrence must be timezone-aware.")
    current = current_utc.astimezone(UTC)
    if rule.frequency is RecurrenceFrequency.INTERVAL:
        candidate = current + timedelta(minutes=rule.interval)
    elif timezone_name is not None:
        local_candidate = _calendar_occurrence(current, rule, timezone_name)
        if local_candidate is None:
            return None
        candidate = local_candidate
    elif rule.frequency is RecurrenceFrequency.DAILY:
        candidate = current + timedelta(days=rule.interval)
    elif rule.frequency is RecurrenceFrequency.WEEKLY:
        candidate = current + timedelta(weeks=rule.interval)
    elif rule.frequency is RecurrenceFrequency.WEEKDAYS:
        candidate = current + timedelta(days=1)
        while candidate.weekday() not in rule.weekdays:
            candidate += timedelta(days=1)
    else:
        year, month = current.year, current.month
        for _ in range(24):
            month += rule.interval
            year += (month - 1) // 12
            month = (month - 1) % 12 + 1
            if current.day <= calendar.monthrange(year, month)[1]:
                candidate = current.replace(year=year, month=month)
                break
        else:
            return None
    return None if rule.end_at_utc and candidate > rule.end_at_utc else candidate


def next_future_occurrence(
    current_utc: datetime,
    rule: RecurrenceRule,
    occurrence_count: int,
    after_utc: datetime,
    timezone_name: str | None = None,
) -> tuple[datetime | None, int]:
    """Advance once, skipping bounded overdue occurrences without replaying them."""

    if after_utc.tzinfo is None:
        raise ModelValidationError("after_utc must be timezone-aware.")
    count = occurrence_count + 1
    candidate = current_utc
    while count < rule.maximum_occurrences:
        next_value = next_occurrence(candidate, rule, timezone_name)
        if next_value is None:
            return None, count
        candidate = next_value
        if candidate > after_utc.astimezone(UTC):
            return candidate, count
        count += 1
    return None, count


def _calendar_occurrence(
    current: datetime,
    rule: RecurrenceRule,
    timezone_name: str,
) -> datetime | None:
    """Advance calendar recurrence in local wall time, skipping DST gaps/folds."""

    zone = configured_timezone(timezone_name)
    local = current.astimezone(zone).replace(tzinfo=None)
    candidate = local
    for _ in range(370):
        if rule.frequency is RecurrenceFrequency.DAILY:
            candidate += timedelta(days=rule.interval)
        elif rule.frequency is RecurrenceFrequency.WEEKLY:
            candidate += timedelta(weeks=rule.interval)
        elif rule.frequency is RecurrenceFrequency.WEEKDAYS:
            candidate += timedelta(days=1)
            while candidate.weekday() not in rule.weekdays:
                candidate += timedelta(days=1)
        else:
            year, month = candidate.year, candidate.month + rule.interval
            year += (month - 1) // 12
            month = (month - 1) % 12 + 1
            if local.day > calendar.monthrange(year, month)[1]:
                candidate = candidate.replace(year=year, month=month, day=1)
                continue
            candidate = candidate.replace(year=year, month=month, day=local.day)
        try:
            return local_datetime_to_utc(candidate, zone)
        except ModelValidationError:
            continue
    return None
