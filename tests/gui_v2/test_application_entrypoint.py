from __future__ import annotations

from omega.__main__ import main
from omega.gui_v2.application import OmegaV2GuiApplication


class FakeRoot:
    def __init__(self) -> None:
        self.mainloop_calls = 0

    def mainloop(self) -> None:
        self.mainloop_calls += 1


def test_v2_application_bootstrap_is_explicit() -> None:
    root = FakeRoot()
    windows = []
    application = OmegaV2GuiApplication(
        root_factory=lambda: root,
        window_factory=lambda created_root, configuration: windows.append(
            (created_root, configuration)
        ),
    )
    assert application.run() == 0
    assert root.mainloop_calls == 1
    assert len(windows) == 1


def test_v2_entry_points_are_lazy_and_terminal_remains_default(
    monkeypatch, capsys
) -> None:
    calls = []

    class ExistingApplication:
        def run(self):
            calls.append("terminal")
            return 0

        def run_gui(self):
            calls.append("v1-gui")
            return 0

    monkeypatch.setattr("omega.__main__.OmegaApplication", ExistingApplication)
    monkeypatch.setattr(
        "omega.gui_v2.application.OmegaV2GuiApplication.check_available",
        lambda: calls.append("v2-check"),
    )

    assert main([]) == 0
    assert main(["--v2-gui-check"]) == 0
    assert calls == ["terminal", "v2-check"]
    assert "Omega V2 GUI support is available" in capsys.readouterr().out
