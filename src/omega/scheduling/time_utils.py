"""Strict local-time interpretation with explicit DST ambiguity rejection."""

from __future__ import annotations

from datetime import UTC, datetime, tzinfo
from zoneinfo import ZoneInfo

from tzlocal import get_localzone

from omega.core.exceptions import ModelValidationError


def configured_timezone(name: str) -> tzinfo:
    """Resolve ``system`` or an already validated IANA timezone name."""

    if name == "system":
        return get_localzone()
    if name.casefold() == "utc":
        return UTC
    return ZoneInfo(name)


def local_datetime_to_utc(value: datetime, zone: tzinfo) -> datetime:
    """Convert a naive wall time, rejecting nonexistent or ambiguous DST times."""

    if value.tzinfo is not None:
        raise ModelValidationError("Local input time must be a naive wall time.")
    candidates: list[datetime] = []
    for fold in (0, 1):
        local = value.replace(tzinfo=zone, fold=fold)
        converted = local.astimezone(UTC)
        round_trip = converted.astimezone(zone).replace(tzinfo=None)
        if round_trip == value and converted not in candidates:
            candidates.append(converted)
    if not candidates:
        raise ModelValidationError(
            "That local time does not exist because of a daylight-saving change."
        )
    if len(candidates) > 1:
        raise ModelValidationError(
            "That local time is ambiguous because of a daylight-saving change."
        )
    return candidates[0]
