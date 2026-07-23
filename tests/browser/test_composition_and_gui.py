"""Application composition and GUI command-routing tests."""

from pathlib import Path

from omega.app import OmegaApplication
from omega.browser import BrowserSessionState, PlaywrightBrowserBackend
from omega.gui.main_window import OmegaMainWindow


def test_application_composes_one_lazy_browser_manager(tmp_path: Path) -> None:
    app = OmegaApplication(database_path=tmp_path / "omega.db")
    assert app.browser_manager.state is BrowserSessionState.STOPPED
    assert isinstance(app.browser_manager.backend, PlaywrightBrowserBackend)
    assert app.browser_manager.backend._playwright is None
    app.shutdown()


def test_gui_browser_controls_submit_normal_commands() -> None:
    class RecordingController:
        def __init__(self) -> None:
            self.commands: list[str] = []

        def submit_command(self, text: str) -> bool:
            self.commands.append(text)
            return True

    window = object.__new__(OmegaMainWindow)
    controller = RecordingController()
    window.controller = controller  # type: ignore[assignment]
    window._open_browser()
    window._list_tabs()
    window._browser_back()
    window._browser_forward()
    window._browser_refresh()
    assert controller.commands == [
        "open browser",
        "list tabs",
        "go back",
        "go forward",
        "refresh page",
    ]
