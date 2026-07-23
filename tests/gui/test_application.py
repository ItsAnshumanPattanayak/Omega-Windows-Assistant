import importlib
import threading
from pathlib import Path

import pytest

from omega.core.exceptions import GuiInitializationError
from omega.gui.application import OmegaGuiApplication


class FakeRoot:
    def __init__(self):
        self.mainloop_calls = 0
        self.scaling = []
        self.tk = self

    def winfo_fpixels(self, _value):
        return 96.0

    def call(self, *values):
        self.scaling.append(values)

    def mainloop(self):
        self.mainloop_calls += 1


def test_gui_import_has_no_root_database_directory_or_thread_side_effect(
    tmp_path: Path,
):
    before = {thread.name for thread in threading.enumerate()}

    importlib.import_module("omega.gui.application")
    importlib.import_module("omega.gui.controller")

    after = {thread.name for thread in threading.enumerate()}
    assert before == after
    assert list(tmp_path.iterdir()) == []


def test_explicit_bootstrap_creates_one_root_and_mainloop():
    root = FakeRoot()
    windows = []
    application = object()

    result = OmegaGuiApplication(
        application,  # type: ignore[arg-type]
        root_factory=lambda: root,
        window_factory=lambda created_root, created_app: windows.append(
            (created_root, created_app)
        ),
    ).run()

    assert result == 0
    assert root.mainloop_calls == 1
    assert windows == [(root, application)]
    assert root.scaling


def test_gui_availability_check_does_not_create_root(monkeypatch):
    calls = []
    monkeypatch.setattr("tkinter.Tk", lambda: calls.append("root"))

    OmegaGuiApplication.check_available()

    assert calls == []


def test_startup_failure_is_reported_as_project_error():
    def fail():
        raise RuntimeError("private Tk diagnostic")

    with pytest.raises(GuiInitializationError, match="desktop interface"):
        OmegaGuiApplication(
            object(),  # type: ignore[arg-type]
            root_factory=fail,
        ).run()
