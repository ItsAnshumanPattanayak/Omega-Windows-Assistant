"""Strict configuration for Omega's local scheduler."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from omega.core.exceptions import ConfigurationError


@dataclass(frozen=True)
class SchedulingConfiguration:
    enabled: bool = True
    timezone: str = "system"
    scheduler_poll_interval_seconds: int = 1
    claim_timeout_seconds: int = 300
    maximum_delivery_batch: int = 50
    maximum_active_items: int = 500
    maximum_title_characters: int = 120
    maximum_message_characters: int = 1000
    maximum_timer_duration_seconds: int = 604800
    maximum_alarm_horizon_days: int = 3650
    maximum_recurring_occurrences: int = 1000
    maximum_snooze_minutes: int = 1440
    default_snooze_minutes: int = 10
    deliver_overdue_items: bool = True
    maximum_overdue_age_seconds: int = 86400
    speak_notifications: bool = False
    restore_pending_items_on_startup: bool = True
    allow_scheduled_commands: bool = False
    allow_recurring_scheduled_commands: bool = False

    @classmethod
    def from_mapping(cls, values: Mapping[str, Any]) -> SchedulingConfiguration:
        defaults = cls()
        allowed = set(defaults.__dataclass_fields__)
        unknown = set(values) - allowed
        if unknown:
            raise ConfigurationError(
                "Unknown scheduling setting(s): " + ", ".join(sorted(unknown))
            )
        data = {key: values.get(key, getattr(defaults, key)) for key in allowed}
        for key in (
            "enabled",
            "deliver_overdue_items",
            "speak_notifications",
            "restore_pending_items_on_startup",
            "allow_scheduled_commands",
            "allow_recurring_scheduled_commands",
        ):
            if not isinstance(data[key], bool):
                raise ConfigurationError(f"scheduling.{key} must be a boolean.")
        if (
            data["allow_scheduled_commands"]
            or data["allow_recurring_scheduled_commands"]
        ):
            raise ConfigurationError(
                "Scheduled command execution must remain disabled."
            )
        if not isinstance(data["timezone"], str) or not data["timezone"].strip():
            raise ConfigurationError(
                "scheduling.timezone must be system or an IANA zone."
            )
        if data["timezone"] != "system":
            try:
                ZoneInfo(data["timezone"])
            except ZoneInfoNotFoundError as error:
                raise ConfigurationError("scheduling.timezone is unknown.") from error
        bounds = {
            "scheduler_poll_interval_seconds": (1, 60),
            "claim_timeout_seconds": (30, 3600),
            "maximum_delivery_batch": (1, 200),
            "maximum_active_items": (1, 5000),
            "maximum_title_characters": (1, 500),
            "maximum_message_characters": (1, 10000),
            "maximum_timer_duration_seconds": (1, 2592000),
            "maximum_alarm_horizon_days": (1, 3650),
            "maximum_recurring_occurrences": (1, 10000),
            "maximum_snooze_minutes": (1, 10080),
            "default_snooze_minutes": (1, 1440),
            "maximum_overdue_age_seconds": (0, 604800),
        }
        for key, (low, high) in bounds.items():
            value = data[key]
            if (
                isinstance(value, bool)
                or not isinstance(value, int)
                or not low <= value <= high
            ):
                raise ConfigurationError(f"scheduling.{key} is outside its safe range.")
        if data["default_snooze_minutes"] > data["maximum_snooze_minutes"]:
            raise ConfigurationError("Default snooze exceeds maximum snooze.")
        return cls(**data)
