"""Bounded application-facing desktop utility services."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from threading import RLock

from omega.desktop_utilities.configuration import DesktopUtilitiesConfiguration
from omega.desktop_utilities.exceptions import (
    ClipboardError,
    DesktopUtilityUnavailableError,
    ScreenshotError,
    WindowMetadataError,
)
from omega.desktop_utilities.models import (
    DisplayInformation,
    ScreenshotRecord,
    ScreenshotRequest,
    ScreenshotTarget,
    WindowInformation,
)
from omega.desktop_utilities.protocols import (
    ClipboardBackend,
    ScreenInformationProvider,
    ScreenshotBackend,
    WindowInformationProvider,
)


class ClipboardService:
    """Explicit, process-local text clipboard workflows; no monitoring/history."""

    def __init__(
        self, configuration: DesktopUtilitiesConfiguration, backend: ClipboardBackend
    ) -> None:
        self.configuration = configuration
        self.backend = backend
        self._last_text: str | None = None

    def write(self, text: str) -> int:
        value = self._validate(text)
        self._enabled()
        self.backend.write_text(value)
        self._last_text = value
        return len(value)

    def read(self) -> str:
        self._enabled()
        try:
            value = self.backend.read_text()
        except ClipboardError:
            raise
        except Exception as error:
            raise ClipboardError("The clipboard is unavailable or locked.") from error
        if value is None:
            raise ClipboardError("Clipboard does not contain supported plain text.")
        normalized = self._validate(value)
        self._last_text = normalized
        return normalized

    def displayed(self) -> tuple[str, bool]:
        value = self.read()
        maximum = self.configuration.maximum_clipboard_display_characters
        return (value[:maximum], len(value) > maximum)

    def search(self, query: str) -> tuple[int, ...]:
        if not query or "\x00" in query or len(query) > 1_000:
            raise ClipboardError("Clipboard search query is invalid.")
        value = self.read().casefold()
        needle = query.casefold()
        indexes: list[int] = []
        start = 0
        while len(indexes) < 100:
            found = value.find(needle, start)
            if found < 0:
                break
            indexes.append(found)
            start = found + max(1, len(needle))
        return tuple(indexes)

    def clear(self) -> None:
        self._enabled()
        try:
            self.backend.clear()
        except Exception as error:
            raise ClipboardError("The clipboard could not be cleared.") from error
        self._last_text = None

    @property
    def last_text(self) -> str:
        if self._last_text is None:
            raise ClipboardError("Read or write clipboard text first.")
        return self._last_text

    def _validate(self, text: str) -> str:
        if not isinstance(text, str) or "\x00" in text:
            raise ClipboardError("Clipboard text is invalid.")
        value = text.replace("\r\n", "\n").replace("\r", "\n")
        if len(value) > self.configuration.maximum_clipboard_characters:
            raise ClipboardError("Clipboard text exceeds the configured limit.")
        return value

    def _enabled(self) -> None:
        if not self.configuration.enabled or not self.configuration.clipboard_enabled:
            raise DesktopUtilityUnavailableError("Clipboard utilities are disabled.")


class ScreenshotService:
    """Explicit screenshot capture and process-local metadata selection."""

    def __init__(
        self,
        configuration: DesktopUtilitiesConfiguration,
        backend: ScreenshotBackend,
        output_root: Path,
        *,
        opener: Callable[[Path], None] | None = None,
        deleter: Callable[[Path], None] | None = None,
    ) -> None:
        self.configuration = configuration
        self.backend = backend
        self.output_root = output_root.resolve()
        self.opener = opener
        self.deleter = deleter
        self._records: list[ScreenshotRecord] = []
        self._current_id: str | None = None
        self._lock = RLock()

    def capture(self, request: ScreenshotRequest) -> ScreenshotRecord:
        self._enabled()
        if request.target is ScreenshotTarget.REGION:
            if not self.configuration.allow_region_capture:
                raise ScreenshotError("Region capture is disabled.")
            assert request.region is not None
            request.region.validate(
                self.configuration.maximum_screenshot_width,
                self.configuration.maximum_screenshot_height,
                self.configuration.maximum_screenshot_pixels,
            )
        if (
            request.target is ScreenshotTarget.VIRTUAL_DESKTOP
            and not self.configuration.allow_full_virtual_desktop_capture
        ):
            raise ScreenshotError("Virtual-desktop capture is disabled.")
        self.output_root.mkdir(parents=True, exist_ok=True)
        suffix = ".png" if self.configuration.screenshot_format == "png" else ".jpg"
        from datetime import UTC, datetime
        from uuid import uuid4

        filename = f"omega-{datetime.now(UTC):%Y%m%dT%H%M%S}-{uuid4().hex[:12]}{suffix}"
        path = (self.output_root / filename).resolve()
        if path.parent != self.output_root:
            raise ScreenshotError("Screenshot output path is unsafe.")
        if path.exists():
            raise ScreenshotError("Screenshot filename collision detected.")
        width, height = self.backend.capture(request, path)
        if (
            width <= 0
            or height <= 0
            or width > self.configuration.maximum_screenshot_width
            or height > self.configuration.maximum_screenshot_height
            or width * height > self.configuration.maximum_screenshot_pixels
        ):
            raise ScreenshotError("Captured screenshot exceeds configured limits.")
        record = ScreenshotRecord.create(
            path,
            width,
            height,
            self.configuration.screenshot_format,
            request.display_id,
        )
        with self._lock:
            self._records.insert(0, record)
            self._records = self._records[
                : self.configuration.maximum_recent_screenshots
            ]
            self._current_id = record.screenshot_id
        return record

    def recent(self) -> tuple[ScreenshotRecord, ...]:
        with self._lock:
            refreshed = tuple(self._refresh(item) for item in self._records)
            self._records = list(refreshed)
            self._current_id = None
            return refreshed

    def select(self, reference: int | None = None) -> ScreenshotRecord:
        with self._lock:
            if reference is not None:
                if isinstance(reference, bool) or not 1 <= reference <= len(
                    self._records
                ):
                    raise ScreenshotError(
                        "That screenshot number is not in the current result set."
                    )
                self._current_id = self._records[reference - 1].screenshot_id
            if self._current_id is None:
                raise ScreenshotError(
                    "List or capture a screenshot before selecting one."
                )
            record = next(
                (
                    item
                    for item in self._records
                    if item.screenshot_id == self._current_id
                ),
                None,
            )
            if record is None:
                raise ScreenshotError("The screenshot selection is stale.")
            record = self._refresh(record)
            if record.missing:
                raise ScreenshotError("The selected screenshot file is missing.")
            return record

    def open_selected(self, reference: int | None = None) -> ScreenshotRecord:
        record = self.select(reference)
        if self.opener is None:
            raise DesktopUtilityUnavailableError("Screenshot opening is unavailable.")
        self.opener(record.path)
        return record

    def delete_selected(self) -> ScreenshotRecord:
        record = self.select()
        if self.deleter is None:
            raise DesktopUtilityUnavailableError(
                "Safe screenshot deletion is unavailable."
            )
        self.deleter(record.path)
        with self._lock:
            self._records = [
                item
                for item in self._records
                if item.screenshot_id != record.screenshot_id
            ]
            self._current_id = None
        return record

    def clear_session(self) -> None:
        self._current_id = None

    def _refresh(self, record: ScreenshotRecord) -> ScreenshotRecord:
        if record.path.exists() == (not record.missing):
            return record
        from dataclasses import replace

        return replace(record, missing=not record.path.exists())

    def _enabled(self) -> None:
        if not self.configuration.enabled or not self.configuration.screenshots_enabled:
            raise DesktopUtilityUnavailableError("Screenshot utilities are disabled.")


class DesktopInformationService:
    def __init__(
        self,
        configuration: DesktopUtilitiesConfiguration,
        screens: ScreenInformationProvider,
        windows: WindowInformationProvider,
    ) -> None:
        self.configuration = configuration
        self.screens = screens
        self.windows = windows
        self._window_ids: tuple[str, ...] = ()
        self._current_window_id: str | None = None

    def displays(self) -> tuple[DisplayInformation, ...]:
        if (
            not self.configuration.enabled
            or not self.configuration.screen_information_enabled
        ):
            raise DesktopUtilityUnavailableError("Screen information is disabled.")
        return self.screens.list_displays()

    def active_window(self) -> WindowInformation:
        self._windows_enabled()
        item = self._sanitize(self.windows.active_window())
        self._window_ids = (item.window_id,)
        self._current_window_id = item.window_id
        return item

    def visible_windows(
        self, query: str | None = None
    ) -> tuple[WindowInformation, ...]:
        self._windows_enabled()
        items = tuple(
            self._sanitize(item)
            for item in self.windows.list_visible_windows(
                self.configuration.maximum_window_results
            )
        )
        if query:
            items = tuple(
                item for item in items if query.casefold() in item.title.casefold()
            )
        self._window_ids = tuple(item.window_id for item in items)
        self._current_window_id = None
        return items

    def select_window(self, reference: int | None = None) -> WindowInformation:
        if reference is not None:
            if isinstance(reference, bool) or not 1 <= reference <= len(
                self._window_ids
            ):
                raise WindowMetadataError(
                    "That window number is not in the current result set."
                )
            self._current_window_id = self._window_ids[reference - 1]
        if self._current_window_id is None:
            raise WindowMetadataError("Select an exact window first.")
        selected_id = self._current_window_id
        current = next(
            (item for item in self.visible_windows() if item.window_id == selected_id),
            None,
        )
        if current is None:
            raise WindowMetadataError("The selected window is stale.")
        self._current_window_id = current.window_id
        return current

    def bring_selected_to_front(self) -> WindowInformation:
        item = self.select_window()
        self.windows.bring_to_front(item.window_id)
        return item

    def clear_session(self) -> None:
        self._window_ids = ()
        self._current_window_id = None

    def _sanitize(self, item: WindowInformation) -> WindowInformation:
        title = item.title.replace("\r", " ").replace("\n", " ")[
            : self.configuration.maximum_window_title_characters
        ]
        return WindowInformation(
            item.window_id, title, item.process_name, item.visible, item.minimized
        )

    def _windows_enabled(self) -> None:
        if (
            not self.configuration.enabled
            or not self.configuration.window_information_enabled
        ):
            raise DesktopUtilityUnavailableError("Window information is disabled.")
