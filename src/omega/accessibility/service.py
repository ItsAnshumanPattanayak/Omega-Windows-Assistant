"""Side-effect-free accessibility state and output adaptation service."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from typing import Any, cast

from omega.accessibility.configuration import AccessibilityConfiguration
from omega.accessibility.models import (
    AccessibilityEvent,
    AccessibilityFeature,
    AccessibilitySettings,
    AccessibilityState,
)
from omega.accessibility.text import terminal_safe_text
from omega.core.exceptions import AccessibilityConfigurationError

AccessibilityEventSink = Callable[[AccessibilityEvent], None]


class AccessibilityService:
    def __init__(
        self,
        configuration: AccessibilityConfiguration,
        *,
        event_sink: AccessibilityEventSink | None = None,
    ) -> None:
        self.configuration = configuration
        self._event_sink = event_sink
        self._settings = AccessibilitySettings(
            enabled=configuration.enabled,
            screen_reader_friendly_mode=configuration.screen_reader_friendly_mode,
            keyboard_navigation_enabled=configuration.keyboard_navigation_enabled,
            show_keyboard_hints=configuration.show_keyboard_hints,
            high_contrast_enabled=configuration.high_contrast_enabled,
            reduced_motion_enabled=configuration.reduced_motion_enabled,
            font_scale=configuration.font_scale,
            confirmation_timeout_multiplier=(
                configuration.confirmation_timeout_multiplier
            ),
            terminal_color_enabled=configuration.terminal_color_enabled,
            terminal_unicode_symbols_enabled=(
                configuration.terminal_unicode_symbols_enabled
            ),
            terminal_screen_reader_mode=configuration.terminal_screen_reader_mode,
            spoken_response_mode=configuration.spoken_response_mode,
        )

    @property
    def settings(self) -> AccessibilitySettings:
        return self._settings

    def update(self, **changes: object) -> AccessibilitySettings:
        allowed = set(AccessibilitySettings.__dataclass_fields__)
        if set(changes) - allowed:
            raise AccessibilityConfigurationError("Accessibility setting is unknown.")
        candidate = replace(self._settings, **cast(Any, changes))
        if not self.configuration.enabled and candidate != self._settings:
            return self._settings
        if not (
            self.configuration.minimum_font_scale
            <= candidate.font_scale
            <= self.configuration.maximum_font_scale
        ):
            raise AccessibilityConfigurationError("Font scale is outside safe bounds.")
        if not (
            1.0
            <= candidate.confirmation_timeout_multiplier
            <= self.configuration.maximum_confirmation_timeout_multiplier
        ):
            raise AccessibilityConfigurationError(
                "Confirmation timeout extension is outside safe bounds."
            )
        if candidate.spoken_response_mode not in {
            "concise",
            "standard",
            "detailed",
        }:
            raise AccessibilityConfigurationError("Spoken response mode is invalid.")
        self._settings = candidate
        self._emit(AccessibilityFeature.TERMINAL_ACCESSIBILITY, "Settings updated")
        return candidate

    def confirmation_timeout(self, base_seconds: float) -> float:
        if base_seconds <= 0:
            raise AccessibilityConfigurationError(
                "Base confirmation timeout must be positive."
            )
        return min(
            base_seconds * self._settings.confirmation_timeout_multiplier,
            base_seconds * self.configuration.maximum_confirmation_timeout_multiplier,
            300.0,
        )

    def terminal_message(self, state: str, message: str) -> str:
        labels = {
            "success": "Success",
            "warning": "Warning",
            "error": "Error",
            "enabled": "Enabled",
            "disabled": "Disabled",
        }
        prefix = labels.get(state.casefold(), state.title())
        result = f"{prefix}: {message}"
        return terminal_safe_text(
            result,
            unicode_symbols=self._settings.terminal_unicode_symbols_enabled,
        )

    def _emit(self, feature: AccessibilityFeature, message: str) -> None:
        if self._event_sink is not None:
            self._event_sink(
                AccessibilityEvent(AccessibilityState.ENABLED, message, feature)
            )


class RecordingAccessibilityEventSink:
    def __init__(self) -> None:
        self.events: list[AccessibilityEvent] = []

    def __call__(self, event: AccessibilityEvent) -> None:
        self.events.append(event)
