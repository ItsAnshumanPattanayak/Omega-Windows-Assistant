"""Immutable accessibility and localization data models."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import StrEnum
from hashlib import sha256
from typing import Final

from omega.core.exceptions import LanguagePackValidationError

_LANGUAGE: Final = re.compile(r"^[a-z]{2,3}(?:-[A-Z]{2})?$")
_LOCALE: Final = re.compile(r"^[a-z]{2,3}(?:[-_][A-Z]{2})?$")
_KEY: Final = re.compile(r"^[a-z][a-z0-9]*(?:[._-][a-z0-9]+)+$")
_VERSION: Final = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")


class AccessibilityFeature(StrEnum):
    KEYBOARD_NAVIGATION = "keyboard_navigation"
    SCREEN_READER_MODE = "screen_reader_mode"
    FONT_SCALING = "font_scaling"
    HIGH_CONTRAST = "high_contrast"
    REDUCED_MOTION = "reduced_motion"
    ACCESSIBLE_CONFIRMATIONS = "accessible_confirmations"
    TERMINAL_ACCESSIBILITY = "terminal_accessibility"
    VOICE_ACCESSIBILITY = "voice_accessibility"


class AccessibilityState(StrEnum):
    ENABLED = "enabled"
    DISABLED = "disabled"
    UNAVAILABLE = "unavailable"


class TextDirection(StrEnum):
    LEFT_TO_RIGHT = "ltr"
    RIGHT_TO_LEFT = "rtl"


@dataclass(frozen=True, slots=True)
class LanguageIdentifier:
    value: str

    def __post_init__(self) -> None:
        if not _LANGUAGE.fullmatch(self.value):
            raise LanguagePackValidationError("Language identifier is invalid.")

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True, slots=True)
class LocaleIdentifier:
    value: str

    def __post_init__(self) -> None:
        if not _LOCALE.fullmatch(self.value):
            raise LanguagePackValidationError("Locale identifier is invalid.")

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True, slots=True)
class MessageKey:
    value: str

    def __post_init__(self) -> None:
        if not _KEY.fullmatch(self.value):
            raise LanguagePackValidationError("Message key is invalid.")

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True, slots=True)
class LocalizedMessage:
    key: MessageKey
    text: str
    language: LanguageIdentifier
    used_fallback: bool = False


@dataclass(frozen=True, slots=True)
class LanguagePackDescriptor:
    """Data-only language-pack metadata; it contains no entry point or callback."""

    display_name: str
    language: LanguageIdentifier
    locale: LocaleIdentifier
    catalog_version: str
    api_version: str = "1.0"
    coverage: float = 1.0
    text_direction: TextDirection = TextDirection.LEFT_TO_RIGHT
    fallback_language: LanguageIdentifier = field(
        default_factory=lambda: LanguageIdentifier("en")
    )
    preview: bool = False

    def __post_init__(self) -> None:
        if not self.display_name.strip() or len(self.display_name) > 100:
            raise LanguagePackValidationError("Language-pack name is invalid.")
        if not _VERSION.fullmatch(self.catalog_version):
            raise LanguagePackValidationError("Catalog version is invalid.")
        if self.api_version != "1.0":
            raise LanguagePackValidationError("Language-pack API is incompatible.")
        if isinstance(self.coverage, bool) or not 0.0 <= self.coverage <= 1.0:
            raise LanguagePackValidationError("Translation coverage is invalid.")
        if self.coverage < 1.0 and not self.preview:
            raise LanguagePackValidationError(
                "Incomplete language packs must be explicitly marked preview."
            )

    def fingerprint(self, canonical_catalog: bytes) -> str:
        return sha256(canonical_catalog).hexdigest()


@dataclass(frozen=True, slots=True)
class AccessibilitySettings:
    enabled: bool = True
    screen_reader_friendly_mode: bool = False
    keyboard_navigation_enabled: bool = True
    show_keyboard_hints: bool = True
    high_contrast_enabled: bool = False
    reduced_motion_enabled: bool = False
    font_scale: float = 1.0
    confirmation_timeout_multiplier: float = 1.0
    terminal_color_enabled: bool = True
    terminal_unicode_symbols_enabled: bool = True
    terminal_screen_reader_mode: bool = False
    spoken_response_mode: str = "standard"


@dataclass(frozen=True, slots=True)
class AccessibilityEvent:
    state: AccessibilityState
    message: str
    feature: AccessibilityFeature | None = None
