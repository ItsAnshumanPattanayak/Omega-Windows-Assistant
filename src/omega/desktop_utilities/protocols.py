"""Testable adapter boundaries for explicit desktop operations."""

from pathlib import Path
from typing import Protocol

from omega.desktop_utilities.models import (
    DisplayInformation,
    ScreenshotRequest,
    WindowInformation,
)


class ClipboardBackend(Protocol):
    def read_text(self) -> str | None: ...
    def write_text(self, text: str) -> None: ...
    def clear(self) -> None: ...


class ScreenshotBackend(Protocol):
    def capture(
        self, request: ScreenshotRequest, output_path: Path
    ) -> tuple[int, int]: ...


class ScreenInformationProvider(Protocol):
    def list_displays(self) -> tuple[DisplayInformation, ...]: ...


class WindowInformationProvider(Protocol):
    def active_window(self) -> WindowInformation: ...
    def list_visible_windows(self, limit: int) -> tuple[WindowInformation, ...]: ...
    def bring_to_front(self, window_id: str) -> None: ...


class SafePathOpener(Protocol):
    def __call__(self, path: Path) -> None: ...


class SafePathDeleter(Protocol):
    def __call__(self, path: Path) -> None: ...
