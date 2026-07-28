"""Conservative Phase 24 personalization configuration."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, fields
from typing import Any

from omega.personalization.exceptions import PreferenceValidationError


@dataclass(frozen=True)
class PersonalizationConfiguration:
    enabled: bool = True
    multiple_profiles_enabled: bool = False
    maximum_profiles: int = 5
    maximum_preference_value_characters: int = 10_000
    maximum_profile_name_characters: int = 80
    maximum_display_name_characters: int = 120
    maximum_export_bytes: int = 1_048_576
    default_response_verbosity: str = "standard"
    default_language: str = "en"
    default_time_format: str = "system"
    default_date_format: str = "system"
    default_unit_system: str = "system"
    persist_session_preferences: bool = False
    enable_personalized_greetings: bool = True
    allow_sensitive_preference_storage: bool = False
    require_confirmation_for_profile_reset: bool = True
    require_confirmation_for_profile_import: bool = True
    require_confirmation_for_profile_delete: bool = True
    expose_preference_resolution_debug: bool = False
    collect_usage_statistics: bool = False
    enable_cloud_sync: bool = False
    enable_behavioral_inference: bool = False

    def __post_init__(self) -> None:
        boolean_fields = [
            item.name for item in fields(self) if item.type in (bool, "bool")
        ]
        if any(not isinstance(getattr(self, name), bool) for name in boolean_fields):
            raise PreferenceValidationError("Personalization switches must be boolean.")
        bounds = {
            "maximum_profiles": (1, 20),
            "maximum_preference_value_characters": (1, 50_000),
            "maximum_profile_name_characters": (1, 120),
            "maximum_display_name_characters": (1, 200),
            "maximum_export_bytes": (1_024, 5_242_880),
        }
        for name, (minimum, maximum) in bounds.items():
            value = getattr(self, name)
            if (
                isinstance(value, bool)
                or not isinstance(value, int)
                or not minimum <= value <= maximum
            ):
                raise PreferenceValidationError(
                    f"personalization.{name} must be between {minimum} and {maximum}."
                )
        if self.default_response_verbosity not in {"concise", "standard", "detailed"}:
            raise PreferenceValidationError(
                "The default response verbosity is invalid."
            )
        if self.default_time_format not in {"system", "12-hour", "24-hour"}:
            raise PreferenceValidationError("The default time format is invalid.")
        if self.default_date_format not in {
            "system",
            "iso",
            "day-first",
            "month-first",
        }:
            raise PreferenceValidationError("The default date format is invalid.")
        if self.default_unit_system not in {"system", "metric", "imperial"}:
            raise PreferenceValidationError("The default unit system is invalid.")
        if any(
            (
                self.allow_sensitive_preference_storage,
                self.collect_usage_statistics,
                self.enable_cloud_sync,
                self.enable_behavioral_inference,
                self.persist_session_preferences,
                self.expose_preference_resolution_debug,
            )
        ):
            raise PreferenceValidationError(
                "Sensitive storage, telemetry, cloud sync, inference, and hidden "
                "persistence are prohibited."
            )

    @classmethod
    def from_mapping(cls, values: Mapping[str, Any]) -> PersonalizationConfiguration:
        known = {item.name for item in fields(cls)}
        unknown = set(values) - known
        if unknown:
            raise PreferenceValidationError(
                "Unknown personalization setting(s): " + ", ".join(sorted(unknown))
            )
        return cls(**dict(values))
