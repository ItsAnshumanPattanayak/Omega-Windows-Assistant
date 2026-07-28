"""Deterministic locale-aware presentation over locale-neutral values."""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from omega.accessibility.models import LocaleIdentifier
from omega.core.exceptions import LanguagePackValidationError


class LocaleFormatter:
    def __init__(
        self,
        locale: str = "en_US",
        *,
        time_format: str = "system",
        date_format: str = "system",
        time_zone: str = "system",
        unit_system: str = "system",
    ) -> None:
        self.locale = LocaleIdentifier(locale).value
        if time_format not in {"system", "12-hour", "24-hour"}:
            raise LanguagePackValidationError("Time format is invalid.")
        if date_format not in {"system", "iso", "day-first", "month-first"}:
            raise LanguagePackValidationError("Date format is invalid.")
        if unit_system not in {"system", "metric", "imperial"}:
            raise LanguagePackValidationError("Unit system is invalid.")
        self.time_format, self.date_format = time_format, date_format
        self.time_zone, self.unit_system = time_zone, unit_system

    def _local(self, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise LanguagePackValidationError("Datetime must be timezone-aware.")
        if self.time_zone == "system":
            return value.astimezone()
        try:
            return value.astimezone(ZoneInfo(self.time_zone))
        except (ZoneInfoNotFoundError, ValueError) as error:
            raise LanguagePackValidationError("Time zone is invalid.") from error

    def format_date(self, value: datetime) -> str:
        local = self._local(value)
        style = self.date_format
        if style == "system":
            style = "day-first" if self.locale in {"en_GB", "hi_IN"} else "month-first"
        return {
            "iso": local.strftime("%Y-%m-%d"),
            "day-first": local.strftime("%d/%m/%Y"),
            "month-first": local.strftime("%m/%d/%Y"),
        }[style]

    def format_time(self, value: datetime) -> str:
        local = self._local(value)
        style = self.time_format
        if style == "system":
            style = "12-hour" if self.locale == "en_US" else "24-hour"
        rendered = (
            local.strftime("%I:%M %p")
            if style == "12-hour"
            else local.strftime("%H:%M")
        )
        return f"{rendered} {local.tzname() or 'UTC'}"

    def format_number(self, value: int | float, *, decimals: int = 0) -> str:
        if isinstance(value, bool) or decimals not in range(0, 7):
            raise LanguagePackValidationError("Number formatting input is invalid.")
        rendered = f"{value:,.{decimals}f}"
        if self.locale == "hi_IN":
            whole, dot, fraction = rendered.replace(",", "").partition(".")
            prefix, tail = whole[:-3], whole[-3:]
            groups: list[str] = []
            while prefix:
                groups.insert(0, prefix[-2:])
                prefix = prefix[:-2]
            rendered = ",".join((*groups, tail)) + (dot + fraction if dot else "")
        return rendered

    def format_percentage(self, value: float) -> str:
        return f"{self.format_number(value * 100, decimals=1)}%"

    def format_file_size(self, byte_count: int) -> str:
        if isinstance(byte_count, bool) or byte_count < 0:
            raise LanguagePackValidationError("File size must be non-negative.")
        amount, unit = float(byte_count), "B"
        for candidate in ("KB", "MB", "GB", "TB"):
            if amount < 1024:
                break
            amount, unit = amount / 1024, candidate
        decimals = 0 if unit == "B" else 1
        return f"{self.format_number(amount, decimals=decimals)} {unit}"

    def format_duration(self, seconds: float) -> str:
        if isinstance(seconds, bool) or seconds < 0:
            raise LanguagePackValidationError("Duration must be non-negative.")
        total = int(round(seconds))
        hours, remainder = divmod(total, 3600)
        minutes, remaining = divmod(remainder, 60)
        parts = []
        if hours:
            parts.append(f"{hours} hr")
        if minutes:
            parts.append(f"{minutes} min")
        if remaining or not parts:
            parts.append(f"{remaining} sec")
        return ", ".join(parts)

    def format_list(self, values: tuple[str, ...]) -> str:
        if not values:
            return ""
        if len(values) == 1:
            return values[0]
        conjunction = " और " if self.locale == "hi_IN" else " and "
        return ", ".join(values[:-1]) + conjunction + values[-1]


DateTimeFormatter = LocaleFormatter
NumberFormatter = LocaleFormatter
