from __future__ import annotations

from datetime import UTC, datetime

import pytest

from omega.accessibility import (
    LocaleFormatter,
    normalize_command_text,
    terminal_safe_text,
)
from omega.core.exceptions import LanguagePackValidationError, UnicodeSafetyError


@pytest.mark.parametrize(
    "value,expected",
    [
        ("  OPEN   CHROME ", "open chrome"),
        ("हिंदी में मदद", "हिंदी में मदद"),
        ("Café", "café"),
        ("ＣＨＲＯＭＥ", "chrome"),
        ("hello\r\nomega", "hello omega"),
        ("👋 Omega", "👋 omega"),
    ],
)
def test_unicode_normalization(value: str, expected: str) -> None:
    assert normalize_command_text(value).text == expected


def test_zero_width_is_removed_and_flagged_for_safety() -> None:
    ordinary = normalize_command_text("he\u200bllo")
    sensitive = normalize_command_text("del\u200bete file", safety_sensitive=True)
    assert ordinary.text == "hello"
    assert ordinary.removed_zero_width is True
    assert sensitive.safety_ambiguous is True


@pytest.mark.parametrize("value", ["bad\x00command", "delete\u202efile", "x\x01y"])
def test_unsafe_controls_are_rejected(value: str) -> None:
    with pytest.raises(UnicodeSafetyError):
        normalize_command_text(value)


def test_terminal_symbol_fallback() -> None:
    assert (
        terminal_safe_text("✓ done — safely", unicode_symbols=False)
        == "OK done - safely"
    )
    assert terminal_safe_text("✓ done", unicode_symbols=True) == "✓ done"


@pytest.mark.parametrize(
    "locale,date_format,expected",
    [
        ("en_US", "month-first", "07/28/2026"),
        ("en_GB", "day-first", "28/07/2026"),
        ("hi_IN", "system", "28/07/2026"),
        ("en_US", "iso", "2026-07-28"),
    ],
)
def test_locale_date_format(locale: str, date_format: str, expected: str) -> None:
    formatter = LocaleFormatter(locale, date_format=date_format, time_zone="UTC")
    assert formatter.format_date(datetime(2026, 7, 28, 13, 5, tzinfo=UTC)) == expected


def test_12_and_24_hour_time_and_zone() -> None:
    value = datetime(2026, 7, 28, 13, 5, tzinfo=UTC)
    assert (
        LocaleFormatter("en_US", time_format="12-hour", time_zone="UTC").format_time(
            value
        )
        == "01:05 PM UTC"
    )
    assert (
        LocaleFormatter("en_GB", time_format="24-hour", time_zone="UTC").format_time(
            value
        )
        == "13:05 UTC"
    )


@pytest.mark.parametrize(
    "locale,value,expected",
    [
        ("en_US", 1234567, "1,234,567"),
        ("hi_IN", 1234567, "12,34,567"),
        ("en_US", 12.5, "12"),
    ],
)
def test_number_formatting(locale: str, value: int | float, expected: str) -> None:
    assert LocaleFormatter(locale).format_number(value) == expected


def test_percentage_size_duration_and_list() -> None:
    formatter = LocaleFormatter("en_US")
    assert formatter.format_percentage(0.125) == "12.5%"
    assert formatter.format_file_size(1536) == "1.5 KB"
    assert formatter.format_duration(3661) == "1 hr, 1 min, 1 sec"
    assert formatter.format_list(("one", "two", "three")) == "one, two and three"


def test_datetime_must_be_aware_and_values_non_negative() -> None:
    formatter = LocaleFormatter()
    with pytest.raises(LanguagePackValidationError):
        formatter.format_date(datetime(2026, 1, 1))
    with pytest.raises(LanguagePackValidationError):
        formatter.format_file_size(-1)
    with pytest.raises(LanguagePackValidationError):
        formatter.format_duration(-1)
