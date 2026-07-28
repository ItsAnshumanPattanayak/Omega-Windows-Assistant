"""Conservative, immutable security hardening configuration."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, fields
from typing import Any

from omega.core.exceptions import SecurityConfigurationError


@dataclass(frozen=True, slots=True)
class SecurityConfiguration:
    enabled: bool = True
    maximum_command_characters: int = 10_000
    maximum_command_tokens: int = 512
    command_rate_limit: int = 60
    command_rate_window_seconds: float = 10.0
    maximum_json_bytes: int = 5_242_880
    maximum_json_depth: int = 20
    maximum_json_items: int = 50_000
    maximum_diagnostic_findings: int = 100
    maximum_log_message_characters: int = 10_000
    maximum_archive_compression_ratio: float = 200.0
    redact_logs: bool = True
    allow_shell_execution: bool = False
    allow_dynamic_code_execution: bool = False
    allow_automatic_email_send: bool = False
    allow_automatic_calendar_mutation: bool = False
    allow_confirmation_bypass: bool = False
    allow_remote_plugin_downloads: bool = False
    allow_automatic_plugin_updates: bool = False
    allow_automatic_model_downloads: bool = False
    allow_external_translation_services: bool = False
    allow_background_clipboard_monitoring: bool = False
    allow_background_screenshot_capture: bool = False
    allow_telemetry: bool = False
    allow_cloud_sync: bool = False

    def __post_init__(self) -> None:
        for item in fields(self):
            if item.type in (bool, "bool") and not isinstance(
                getattr(self, item.name), bool
            ):
                raise SecurityConfigurationError(
                    f"security.{item.name} must be boolean."
                )
        bounds: dict[str, tuple[float, float]] = {
            "maximum_command_characters": (1, 100_000),
            "maximum_command_tokens": (1, 10_000),
            "command_rate_limit": (1, 1_000),
            "command_rate_window_seconds": (0.1, 3_600),
            "maximum_json_bytes": (1_024, 52_428_800),
            "maximum_json_depth": (1, 100),
            "maximum_json_items": (1, 1_000_000),
            "maximum_diagnostic_findings": (1, 1_000),
            "maximum_log_message_characters": (256, 100_000),
            "maximum_archive_compression_ratio": (1.0, 1_000.0),
        }
        for name, (minimum, maximum) in bounds.items():
            value = getattr(self, name)
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not (minimum <= float(value) <= maximum)
            ):
                raise SecurityConfigurationError(
                    f"security.{name} is outside its safe bounds."
                )
        prohibited = (
            self.allow_shell_execution,
            self.allow_dynamic_code_execution,
            self.allow_automatic_email_send,
            self.allow_automatic_calendar_mutation,
            self.allow_confirmation_bypass,
            self.allow_remote_plugin_downloads,
            self.allow_automatic_plugin_updates,
            self.allow_automatic_model_downloads,
            self.allow_external_translation_services,
            self.allow_background_clipboard_monitoring,
            self.allow_background_screenshot_capture,
            self.allow_telemetry,
            self.allow_cloud_sync,
        )
        if any(prohibited):
            raise SecurityConfigurationError(
                "Mandatory Phase 26 security protections cannot be enabled."
            )
        if not self.enabled or not self.redact_logs:
            raise SecurityConfigurationError(
                "Mandatory Phase 26 security protections cannot be disabled."
            )

    @classmethod
    def from_mapping(cls, values: Mapping[str, Any]) -> SecurityConfiguration:
        known = {item.name for item in fields(cls)}
        unknown = set(values) - known
        if unknown:
            raise SecurityConfigurationError(
                "Unknown security setting(s): " + ", ".join(sorted(unknown))
            )
        return cls(**dict(values))
