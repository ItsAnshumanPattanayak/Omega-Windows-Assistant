"""Typed, privacy-minimized desktop-utility records."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from uuid import uuid4

from omega.desktop_utilities.exceptions import DesktopUtilityError


class ScreenshotTarget(StrEnum):
    PRIMARY = "primary"
    DISPLAY = "display"
    VIRTUAL_DESKTOP = "virtual_desktop"
    REGION = "region"


@dataclass(frozen=True)
class ScreenshotRegion:
    x: int
    y: int
    width: int
    height: int

    def validate(
        self, maximum_width: int, maximum_height: int, maximum_pixels: int
    ) -> None:
        values = (self.x, self.y, self.width, self.height)
        if any(
            isinstance(value, bool) or not isinstance(value, int) for value in values
        ):
            raise DesktopUtilityError("Screenshot coordinates must be integers.")
        if self.width <= 0 or self.height <= 0:
            raise DesktopUtilityError("Screenshot dimensions must be positive.")
        if (
            self.width > maximum_width
            or self.height > maximum_height
            or self.width * self.height > maximum_pixels
        ):
            raise DesktopUtilityError("Screenshot region exceeds configured limits.")


@dataclass(frozen=True)
class ScreenshotRequest:
    target: ScreenshotTarget = ScreenshotTarget.PRIMARY
    display_id: str | None = None
    region: ScreenshotRegion | None = None

    def __post_init__(self) -> None:
        if self.target is ScreenshotTarget.DISPLAY and not self.display_id:
            raise DesktopUtilityError("Selected-display capture requires a display ID.")
        if self.target is ScreenshotTarget.REGION and self.region is None:
            raise DesktopUtilityError("Region capture requires coordinates.")
        if self.target is not ScreenshotTarget.REGION and self.region is not None:
            raise DesktopUtilityError("Coordinates are only valid for region capture.")


@dataclass(frozen=True)
class ScreenshotRecord:
    screenshot_id: str
    path: Path
    width: int
    height: int
    image_format: str
    display_id: str | None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    missing: bool = False

    def __post_init__(self) -> None:
        if not self.screenshot_id.strip() or not self.path.is_absolute():
            raise DesktopUtilityError("Screenshot identity or path is invalid.")
        if (
            self.width <= 0
            or self.height <= 0
            or self.image_format not in {"png", "jpeg"}
        ):
            raise DesktopUtilityError("Screenshot metadata is invalid.")
        if self.created_at.tzinfo is None or self.created_at.utcoffset() is None:
            raise DesktopUtilityError("Screenshot timestamp must be timezone-aware.")

    @classmethod
    def create(
        cls,
        path: Path,
        width: int,
        height: int,
        image_format: str,
        display_id: str | None,
    ) -> ScreenshotRecord:
        return cls(str(uuid4()), path, width, height, image_format, display_id)


@dataclass(frozen=True)
class DisplayInformation:
    display_id: str
    x: int
    y: int
    width: int
    height: int
    primary: bool = False
    scaling_percent: int | None = None
    orientation: str | None = None

    def __post_init__(self) -> None:
        if not self.display_id.strip() or self.width <= 0 or self.height <= 0:
            raise DesktopUtilityError("Display metadata is invalid.")


@dataclass(frozen=True)
class WindowInformation:
    window_id: str
    title: str
    process_name: str | None = None
    visible: bool = True
    minimized: bool = False

    def __post_init__(self) -> None:
        if not self.window_id.strip() or "\x00" in self.title:
            raise DesktopUtilityError("Window metadata is invalid.")
