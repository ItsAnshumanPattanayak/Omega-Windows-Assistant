"""Conservative desktop-utility configuration without private paths."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from omega.desktop_utilities.exceptions import DesktopUtilityConfigurationError


@dataclass(frozen=True)
class DesktopUtilitiesConfiguration:
    enabled: bool = True
    clipboard_enabled: bool = True
    screenshots_enabled: bool = True
    screen_information_enabled: bool = True
    window_information_enabled: bool = True
    clipboard_history_enabled: bool = False
    maximum_clipboard_characters: int = 50_000
    maximum_clipboard_display_characters: int = 5_000
    maximum_window_results: int = 25
    maximum_window_title_characters: int = 300
    screenshot_format: str = "png"
    screenshot_directory: str | None = None
    maximum_screenshot_width: int = 16_384
    maximum_screenshot_height: int = 16_384
    maximum_screenshot_pixels: int = 67_108_864
    maximum_recent_screenshots: int = 50
    allow_full_virtual_desktop_capture: bool = True
    allow_region_capture: bool = True
    require_confirmation_for_clear_clipboard: bool = True
    require_confirmation_for_delete_screenshot: bool = True
    allow_background_clipboard_monitoring: bool = False
    allow_background_screenshot_capture: bool = False

    @classmethod
    def from_mapping(cls, values: Mapping[str, Any]) -> DesktopUtilitiesConfiguration:
        unknown = set(values).difference(cls.__dataclass_fields__)
        if unknown:
            raise DesktopUtilityConfigurationError(
                "Unknown desktop_utilities setting(s): " + ", ".join(sorted(unknown))
            )
        try:
            return cls(**values)
        except TypeError as error:
            raise DesktopUtilityConfigurationError(
                "Desktop utilities configuration is invalid."
            ) from error

    def __post_init__(self) -> None:
        booleans = (
            "enabled",
            "clipboard_enabled",
            "screenshots_enabled",
            "screen_information_enabled",
            "window_information_enabled",
            "clipboard_history_enabled",
            "allow_full_virtual_desktop_capture",
            "allow_region_capture",
            "require_confirmation_for_clear_clipboard",
            "require_confirmation_for_delete_screenshot",
            "allow_background_clipboard_monitoring",
            "allow_background_screenshot_capture",
        )
        if any(not isinstance(getattr(self, name), bool) for name in booleans):
            raise DesktopUtilityConfigurationError(
                "Desktop utility policy flags must be booleans."
            )
        bounds = {
            "maximum_clipboard_characters": (1, 1_000_000),
            "maximum_clipboard_display_characters": (1, 100_000),
            "maximum_window_results": (1, 200),
            "maximum_window_title_characters": (1, 2_000),
            "maximum_screenshot_width": (1, 32_768),
            "maximum_screenshot_height": (1, 32_768),
            "maximum_screenshot_pixels": (1, 268_435_456),
            "maximum_recent_screenshots": (1, 500),
        }
        for name, (minimum, maximum) in bounds.items():
            value = getattr(self, name)
            if (
                isinstance(value, bool)
                or not isinstance(value, int)
                or not minimum <= value <= maximum
            ):
                raise DesktopUtilityConfigurationError(
                    f"desktop_utilities.{name} must be between {minimum} and {maximum}."
                )
        if (
            self.maximum_clipboard_display_characters
            > self.maximum_clipboard_characters
        ):
            raise DesktopUtilityConfigurationError(
                "Clipboard display limit cannot exceed the clipboard content limit."
            )
        if self.screenshot_format not in {"png", "jpeg"}:
            raise DesktopUtilityConfigurationError(
                "desktop_utilities.screenshot_format must be png or jpeg."
            )
        if self.screenshot_directory is not None:
            raise DesktopUtilityConfigurationError(
                "Tracked screenshot_directory must remain null; use the runtime "
                "data directory."
            )
        if self.clipboard_history_enabled:
            raise DesktopUtilityConfigurationError(
                "Persistent clipboard history is deferred and must remain disabled."
            )
        if (
            self.allow_background_clipboard_monitoring
            or self.allow_background_screenshot_capture
        ):
            raise DesktopUtilityConfigurationError(
                "Background clipboard and screenshot capture must remain disabled."
            )
        if (
            not self.require_confirmation_for_clear_clipboard
            or not self.require_confirmation_for_delete_screenshot
        ):
            raise DesktopUtilityConfigurationError(
                "Destructive desktop utility confirmations must remain enabled."
            )
