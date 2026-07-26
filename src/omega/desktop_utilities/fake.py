"""Zero-device, zero-network desktop utility fakes."""

from pathlib import Path

from omega.desktop_utilities.exceptions import UnsupportedClipboardFormatError
from omega.desktop_utilities.models import (
    DisplayInformation,
    ScreenshotRequest,
    WindowInformation,
)


class FakeClipboardBackend:
    def __init__(self, text: str | None = "") -> None:
        self.text = text
        self.locked = False
        self.operations = 0

    def read_text(self) -> str | None:
        self.operations += 1
        if self.locked:
            raise RuntimeError("clipboard locked")
        if self.text is None:
            raise UnsupportedClipboardFormatError(
                "Clipboard does not contain supported plain text."
            )
        return self.text

    def write_text(self, text: str) -> None:
        self.operations += 1
        if self.locked:
            raise RuntimeError("clipboard locked")
        self.text = text

    def clear(self) -> None:
        self.operations += 1
        if self.locked:
            raise RuntimeError("clipboard locked")
        self.text = ""


class FakeScreenshotBackend:
    def __init__(self, width: int = 1280, height: int = 720) -> None:
        self.width = width
        self.height = height
        self.capture_count = 0
        self.real_desktop_operations = 0
        self.network_operations = 0

    def capture(self, request: ScreenshotRequest, output_path: Path) -> tuple[int, int]:
        del request
        output_path.write_bytes(b"\x89PNG\r\n\x1a\nOMEGA_FAKE")
        self.capture_count += 1
        return self.width, self.height


class FakeScreenInformationProvider:
    def __init__(self, displays: tuple[DisplayInformation, ...] | None = None) -> None:
        self.displays = displays or (
            DisplayInformation("display-1", 0, 0, 1920, 1080, True),
        )
        self.real_display_operations = 0

    def list_displays(self) -> tuple[DisplayInformation, ...]:
        return self.displays


class FakeWindowInformationProvider:
    def __init__(self, windows: tuple[WindowInformation, ...] | None = None) -> None:
        self.windows = windows or (
            WindowInformation("window-1", "Editor", "editor.exe"),
        )
        self.foreground_ids: list[str] = []
        self.real_window_operations = 0

    def active_window(self) -> WindowInformation:
        if not self.windows:
            raise RuntimeError("no active window")
        return self.windows[0]

    def list_visible_windows(self, limit: int) -> tuple[WindowInformation, ...]:
        return self.windows[:limit]

    def bring_to_front(self, window_id: str) -> None:
        if not any(item.window_id == window_id for item in self.windows):
            raise RuntimeError("window missing")
        self.foreground_ids.append(window_id)
