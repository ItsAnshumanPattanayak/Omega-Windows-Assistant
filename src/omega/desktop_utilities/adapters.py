"""Lazy local adapters; optional capabilities fail safely when unavailable."""

from __future__ import annotations

import os
import sys
from importlib import import_module
from pathlib import Path
from typing import Any

from omega.desktop_utilities.exceptions import (
    ClipboardError,
    DesktopUtilityUnavailableError,
    DisplayUnavailableError,
    UnsupportedClipboardFormatError,
    WindowMetadataError,
)
from omega.desktop_utilities.models import (
    DisplayInformation,
    ScreenshotRequest,
    ScreenshotTarget,
    WindowInformation,
)


class TkClipboardBackend:
    """Explicit clipboard access through a short-lived hidden tkinter root."""

    @staticmethod
    def _root() -> Any:
        try:
            import tkinter

            root = tkinter.Tk()
            root.withdraw()
            return root
        except Exception as error:
            raise ClipboardError("The clipboard is unavailable or locked.") from error

    def read_text(self) -> str | None:
        root = self._root()
        try:
            try:
                return str(root.clipboard_get())
            except Exception as error:
                raise UnsupportedClipboardFormatError(
                    "Clipboard does not contain supported plain text."
                ) from error
        finally:
            root.destroy()

    def write_text(self, text: str) -> None:
        root = self._root()
        try:
            root.clipboard_clear()
            root.clipboard_append(text)
            root.update()
        except Exception as error:
            raise ClipboardError("The clipboard could not be updated.") from error
        finally:
            root.destroy()

    def clear(self) -> None:
        root = self._root()
        try:
            root.clipboard_clear()
            root.update()
        except Exception as error:
            raise ClipboardError("The clipboard could not be cleared.") from error
        finally:
            root.destroy()


class PillowScreenshotBackend:
    """Lazy optional Pillow ImageGrab adapter; never imported at module import."""

    def capture(self, request: ScreenshotRequest, output_path: Path) -> tuple[int, int]:
        if request.target is ScreenshotTarget.DISPLAY:
            raise DesktopUtilityUnavailableError(
                "Selected-display capture is unavailable with this adapter."
            )
        try:
            image_grab = import_module("PIL.ImageGrab")
        except ImportError as error:
            raise DesktopUtilityUnavailableError(
                "Screenshot capture requires the optional Pillow dependency."
            ) from error
        bbox = None
        all_screens = request.target is ScreenshotTarget.VIRTUAL_DESKTOP
        if request.region is not None:
            item = request.region
            bbox = (item.x, item.y, item.x + item.width, item.y + item.height)
        try:
            image = image_grab.grab(bbox=bbox, all_screens=all_screens)
            image.save(output_path)
            return int(image.width), int(image.height)
        except Exception as error:
            raise DesktopUtilityUnavailableError(
                "Screenshot capture failed safely."
            ) from error


class TkScreenInformationProvider:
    def list_displays(self) -> tuple[DisplayInformation, ...]:
        try:
            import tkinter

            root = tkinter.Tk()
            root.withdraw()
            try:
                return (
                    DisplayInformation(
                        "primary",
                        0,
                        0,
                        root.winfo_screenwidth(),
                        root.winfo_screenheight(),
                        True,
                    ),
                )
            finally:
                root.destroy()
        except Exception as error:
            raise DisplayUnavailableError("Display metadata is unavailable.") from error


class WindowsWindowInformationProvider:
    """Minimal Win32 title/visibility adapter without content inspection."""

    def __init__(self) -> None:
        if sys.platform != "win32":
            raise WindowMetadataError("Window metadata is only available on Windows.")

    @staticmethod
    def _user32() -> Any:
        import ctypes

        return ctypes.windll.user32

    def _window(self, handle: int) -> WindowInformation:
        import ctypes

        user32 = self._user32()
        length = int(user32.GetWindowTextLengthW(handle))
        buffer = ctypes.create_unicode_buffer(min(length + 1, 2001))
        user32.GetWindowTextW(handle, buffer, len(buffer))
        return WindowInformation(
            str(handle),
            buffer.value,
            None,
            bool(user32.IsWindowVisible(handle)),
            bool(user32.IsIconic(handle)),
        )

    def active_window(self) -> WindowInformation:
        handle = int(self._user32().GetForegroundWindow())
        if not handle:
            raise WindowMetadataError("No active window is available.")
        return self._window(handle)

    def list_visible_windows(self, limit: int) -> tuple[WindowInformation, ...]:
        import ctypes

        items: list[WindowInformation] = []
        callback_type = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_int, ctypes.c_int)

        def visit(handle: int, extra: int) -> bool:
            del extra
            if len(items) >= limit:
                return False
            item = self._window(handle)
            if item.visible and item.title.strip():
                items.append(item)
            return True

        self._user32().EnumWindows(callback_type(visit), 0)
        return tuple(items)

    def bring_to_front(self, window_id: str) -> None:
        if not window_id.isdigit() or not self._user32().SetForegroundWindow(
            int(window_id)
        ):
            raise WindowMetadataError(
                "The selected window could not be brought forward."
            )


class WindowsPathOpener:
    """Open one already validated local path without a command shell."""

    def __call__(self, path: Path) -> None:
        if sys.platform != "win32" or not path.is_file():
            raise DesktopUtilityUnavailableError("The screenshot cannot be opened.")
        os.startfile(path)
