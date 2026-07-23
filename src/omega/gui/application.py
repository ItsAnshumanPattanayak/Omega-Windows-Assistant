"""Explicit optional tkinter bootstrap with no import-time UI side effects."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from omega.core.exceptions import GuiInitializationError

if TYPE_CHECKING:
    from omega.app import OmegaApplication


class OmegaGuiApplication:
    """Create and run the Tk application only when explicitly requested."""

    def __init__(
        self,
        application: OmegaApplication,
        *,
        root_factory: Callable[[], Any] | None = None,
        window_factory: Callable[[Any, OmegaApplication], Any] | None = None,
    ) -> None:
        self.application = application
        self._root_factory = root_factory
        self._window_factory = window_factory

    def run(self) -> int:
        """Create one root, compose one main window, and run one main loop."""

        try:
            if self._root_factory is None:
                import tkinter as tk

                root = tk.Tk()
            else:
                root = self._root_factory()
            self._configure_scaling(root)
            if self._window_factory is None:
                from omega.gui.main_window import OmegaMainWindow

                window = OmegaMainWindow(root, self.application)
            else:
                window = self._window_factory(root, self.application)
            root.mainloop()
            del window
            return 0
        except Exception as error:
            raise GuiInitializationError(
                "Omega could not start the optional desktop interface."
            ) from error

    @staticmethod
    def check_available() -> None:
        """Verify tkinter imports without creating a root or database."""

        try:
            import tkinter

            if not hasattr(tkinter, "Tk"):
                raise ImportError("tkinter does not provide Tk")
        except ImportError as error:
            raise GuiInitializationError(
                "The optional tkinter desktop interface is unavailable."
            ) from error

    @staticmethod
    def _configure_scaling(root: Any) -> None:
        try:
            pixels_per_inch = float(root.winfo_fpixels("1i"))
            root.tk.call("tk", "scaling", max(1.0, pixels_per_inch / 72.0))
        except (AttributeError, TypeError, ValueError):
            return
