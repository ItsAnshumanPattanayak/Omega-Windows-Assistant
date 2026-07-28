"""Conservative Phase 25 accessibility and localization configuration."""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass, fields
from typing import Any, TypeVar

from omega.core.exceptions import AccessibilityConfigurationError

_LANGUAGE = re.compile(r"^[a-z]{2,3}(?:-[A-Z]{2})?$")
_LOCALE = re.compile(r"^[a-z]{2,3}(?:[-_][A-Z]{2})?$")


_ConfigurationT = TypeVar("_ConfigurationT")


def _strict_mapping(
    cls: type[_ConfigurationT], values: Mapping[str, Any]
) -> _ConfigurationT:
    known = set(getattr(cls, "__dataclass_fields__", {}))
    unknown = set(values) - known
    if unknown:
        raise AccessibilityConfigurationError(
            "Unknown accessibility/localization setting(s): "
            + ", ".join(sorted(unknown))
        )
    return cls(**dict(values))


@dataclass(frozen=True)
class AccessibilityConfiguration:
    """Validated UI, terminal, confirmation, and speech accessibility policy."""

    enabled: bool = True
    screen_reader_friendly_mode: bool = False
    keyboard_navigation_enabled: bool = True
    show_keyboard_hints: bool = True
    high_contrast_enabled: bool = False
    reduced_motion_enabled: bool = False
    font_scale: float = 1.0
    minimum_font_scale: float = 0.8
    maximum_font_scale: float = 2.0
    confirmation_timeout_multiplier: float = 1.0
    maximum_confirmation_timeout_multiplier: float = 3.0
    terminal_color_enabled: bool = True
    terminal_unicode_symbols_enabled: bool = True
    terminal_screen_reader_mode: bool = False
    spoken_response_mode: str = "standard"

    def __post_init__(self) -> None:
        for item in fields(self):
            if item.type in (bool, "bool") and not isinstance(
                getattr(self, item.name), bool
            ):
                raise AccessibilityConfigurationError(
                    f"accessibility.{item.name} must be boolean."
                )
        numeric = (
            self.minimum_font_scale,
            self.font_scale,
            self.maximum_font_scale,
        )
        if any(isinstance(value, bool) for value in numeric) or not (
            0.5 <= numeric[0] <= numeric[1] <= numeric[2] <= 3.0
        ):
            raise AccessibilityConfigurationError(
                "Accessibility font scales must be ordered between 0.5 and 3.0."
            )
        multipliers = (
            self.confirmation_timeout_multiplier,
            self.maximum_confirmation_timeout_multiplier,
        )
        if any(isinstance(value, bool) for value in multipliers) or not (
            1.0 <= multipliers[0] <= multipliers[1] <= 5.0
        ):
            raise AccessibilityConfigurationError(
                "Confirmation timeout multipliers must be ordered between 1 and 5."
            )
        if self.spoken_response_mode not in {"concise", "standard", "detailed"}:
            raise AccessibilityConfigurationError(
                "accessibility.spoken_response_mode is invalid."
            )

    @classmethod
    def from_mapping(cls, values: Mapping[str, Any]) -> AccessibilityConfiguration:
        return _strict_mapping(cls, values)


@dataclass(frozen=True)
class LocalizationConfiguration:
    """Validated local-only catalog policy with conservative external boundaries."""

    enabled: bool = True
    default_language: str = "en"
    default_locale: str = "en_US"
    fallback_language: str = "en"
    allow_partial_language_packs: bool = False
    maximum_catalog_bytes: int = 1_048_576
    maximum_catalog_entries: int = 10_000
    maximum_message_characters: int = 10_000
    maximum_command_aliases_per_intent: int = 50
    allow_external_translation_services: bool = False
    automatically_download_language_packs: bool = False
    allow_ai_translation_drafts: bool = False

    def __post_init__(self) -> None:
        for item in fields(self):
            if item.type in (bool, "bool") and not isinstance(
                getattr(self, item.name), bool
            ):
                raise AccessibilityConfigurationError(
                    f"localization.{item.name} must be boolean."
                )
        if not _LANGUAGE.fullmatch(self.default_language) or not _LANGUAGE.fullmatch(
            self.fallback_language
        ):
            raise AccessibilityConfigurationError("Language identifier is invalid.")
        if not _LOCALE.fullmatch(self.default_locale):
            raise AccessibilityConfigurationError("Locale identifier is invalid.")
        bounds = {
            "maximum_catalog_bytes": (1_024, 5_242_880),
            "maximum_catalog_entries": (1, 50_000),
            "maximum_message_characters": (1, 50_000),
            "maximum_command_aliases_per_intent": (1, 100),
        }
        for name, (minimum, maximum) in bounds.items():
            value = getattr(self, name)
            if (
                isinstance(value, bool)
                or not isinstance(value, int)
                or not (minimum <= value <= maximum)
            ):
                raise AccessibilityConfigurationError(
                    f"localization.{name} is outside its safe bounds."
                )
        if self.allow_external_translation_services:
            raise AccessibilityConfigurationError(
                "External translation services are prohibited by Phase 25."
            )
        if self.automatically_download_language_packs:
            raise AccessibilityConfigurationError(
                "Automatic language-pack downloads are prohibited."
            )

    @classmethod
    def from_mapping(cls, values: Mapping[str, Any]) -> LocalizationConfiguration:
        return _strict_mapping(cls, values)
