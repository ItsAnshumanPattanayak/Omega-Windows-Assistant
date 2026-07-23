"""Strict configuration for bounded Windows system features."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from omega.core.exceptions import ConfigurationError

_KEYS = frozenset(
    {
        "enabled",
        "information_enabled",
        "audio_control_enabled",
        "brightness_control_enabled",
        "process_listing_enabled",
        "process_termination_enabled",
        "settings_pages_enabled",
        "power_actions_enabled",
        "lock_enabled",
        "shutdown_enabled",
        "restart_enabled",
        "sign_out_enabled",
        "sleep_enabled",
        "hibernate_enabled",
        "maximum_process_results",
        "maximum_disk_results",
        "maximum_network_results",
        "minimum_volume_percent",
        "maximum_volume_percent",
        "minimum_brightness_percent",
        "maximum_brightness_percent",
        "maximum_control_increment_percent",
        "power_confirmation_timeout_seconds",
        "power_countdown_seconds",
        "allow_cancel_power_countdown",
    }
)


@dataclass(frozen=True)
class SystemConfiguration:
    """Validated policy; unsafe capabilities cannot be enabled by YAML."""

    enabled: bool = True
    information_enabled: bool = True
    audio_control_enabled: bool = True
    brightness_control_enabled: bool = True
    process_listing_enabled: bool = True
    process_termination_enabled: bool = False
    settings_pages_enabled: bool = True
    power_actions_enabled: bool = True
    lock_enabled: bool = True
    shutdown_enabled: bool = True
    restart_enabled: bool = True
    sign_out_enabled: bool = True
    sleep_enabled: bool = True
    hibernate_enabled: bool = False
    maximum_process_results: int = 50
    maximum_disk_results: int = 20
    maximum_network_results: int = 20
    minimum_volume_percent: int = 0
    maximum_volume_percent: int = 100
    minimum_brightness_percent: int = 10
    maximum_brightness_percent: int = 100
    maximum_control_increment_percent: int = 25
    power_confirmation_timeout_seconds: int = 30
    power_countdown_seconds: int = 10
    allow_cancel_power_countdown: bool = True

    @classmethod
    def from_mapping(cls, values: Mapping[str, Any]) -> SystemConfiguration:
        unknown = set(values).difference(_KEYS)
        if unknown:
            raise ConfigurationError(
                "Unknown system setting(s): " + ", ".join(sorted(unknown))
            )
        defaults = cls()
        merged = {key: values.get(key, getattr(defaults, key)) for key in _KEYS}
        boolean_keys = {
            key for key in _KEYS if isinstance(getattr(defaults, key), bool)
        }
        for key in boolean_keys:
            if not isinstance(merged[key], bool):
                raise ConfigurationError(f"system.{key} must be a boolean.")
        if merged["process_termination_enabled"] is not False:
            raise ConfigurationError(
                "Generic system process termination must remain disabled."
            )
        limits = {
            "maximum_process_results": (1, 200),
            "maximum_disk_results": (1, 50),
            "maximum_network_results": (1, 100),
            "minimum_volume_percent": (0, 100),
            "maximum_volume_percent": (0, 100),
            "minimum_brightness_percent": (1, 100),
            "maximum_brightness_percent": (1, 100),
            "maximum_control_increment_percent": (1, 50),
            "power_confirmation_timeout_seconds": (1, 300),
            "power_countdown_seconds": (0, 60),
        }
        for key, (minimum, maximum) in limits.items():
            value = merged[key]
            if (
                isinstance(value, bool)
                or not isinstance(value, int)
                or not minimum <= value <= maximum
            ):
                raise ConfigurationError(
                    f"system.{key} must be between {minimum} and {maximum}."
                )
        if merged["minimum_volume_percent"] > merged["maximum_volume_percent"]:
            raise ConfigurationError("System volume bounds are inconsistent.")
        if merged["minimum_brightness_percent"] > merged["maximum_brightness_percent"]:
            raise ConfigurationError("System brightness bounds are inconsistent.")
        return cls(**merged)
