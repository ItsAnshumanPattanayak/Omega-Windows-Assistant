"""Explicit Omega V2 GUI bootstrap with no import-time UI side effects."""

from __future__ import annotations

import importlib
from collections.abc import Callable
from typing import Any

from omega.core.exceptions import GuiInitializationError, OmegaError
from omega.gui_v2.assets import resolve_gui_asset
from omega.gui_v2.configuration import V2GuiConfiguration


class OmegaV2GuiApplication:
    """Create and run the Phase 1 GUI only when explicitly requested."""

    def __init__(
        self,
        configuration: V2GuiConfiguration | None = None,
        *,
        root_factory: Callable[[], Any] | None = None,
        window_factory: Callable[[Any, V2GuiConfiguration], Any] | None = None,
    ) -> None:
        self.configuration = configuration or V2GuiConfiguration()
        self._root_factory = root_factory
        self._window_factory = window_factory

    def run(self) -> int:
        try:
            if self._root_factory is None:
                import tkinter as tk

                root = tk.Tk()
            else:
                root = self._root_factory()
            if self._window_factory is None:
                from omega.gui_v2.main_window import OmegaV2MainWindow

                window = OmegaV2MainWindow(root, self.configuration)
            else:
                window = self._window_factory(root, self.configuration)
            root.mainloop()
            del window
            return 0
        except Exception as error:
            raise GuiInitializationError(
                "Omega V2 could not start the desktop interface safely."
            ) from error

    @staticmethod
    def check_available() -> None:
        """Validate the toolkit, media dependencies, and asset without a window."""

        try:
            tkinter = importlib.import_module("tkinter")
            cv2 = importlib.import_module("cv2")
            importlib.import_module("PIL.Image")
            importlib.import_module("PIL.ImageTk")

            if not hasattr(tkinter, "Tk") or not hasattr(cv2, "VideoCapture"):
                raise ImportError("tkinter does not provide Tk")
            configuration = V2GuiConfiguration()
            video_path = resolve_gui_asset(configuration.video_asset_relative_path)
        except (ImportError, OmegaError) as error:
            raise GuiInitializationError(
                "Omega V2 desktop support is unavailable."
            ) from error
        if not video_path.is_file():
            raise GuiInitializationError("The Omega V2 animation asset is unavailable.")
