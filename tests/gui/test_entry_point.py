from omega.__main__ import main


def test_terminal_mode_is_preserved(monkeypatch):
    calls = []

    class Application:
        def run(self):
            calls.append("terminal")
            return 0

        def run_gui(self):
            calls.append("gui")
            return 0

    monkeypatch.setattr("omega.__main__.OmegaApplication", Application)

    assert main([]) == 0
    assert calls == ["terminal"]


def test_gui_mode_is_explicit(monkeypatch):
    calls = []

    class Application:
        def run(self):
            calls.append("terminal")
            return 0

        def run_gui(self):
            calls.append("gui")
            return 0

    monkeypatch.setattr("omega.__main__.OmegaApplication", Application)

    assert main(["--gui"]) == 0
    assert calls == ["gui"]


def test_gui_check_and_invalid_arguments(monkeypatch, capsys):
    checks = []
    monkeypatch.setattr(
        "omega.gui.application.OmegaGuiApplication.check_available",
        lambda: checks.append("checked"),
    )

    assert main(["--gui-check"]) == 0
    assert checks == ["checked"]
    assert main(["--unknown"]) == 2
    assert "Omega argument error" in capsys.readouterr().err


def test_help_does_not_initialize_application(monkeypatch, capsys):
    monkeypatch.setattr(
        "omega.__main__.OmegaApplication",
        lambda: (_ for _ in ()).throw(AssertionError("must not initialize")),
    )

    assert main(["--help"]) == 0
    assert "--gui" in capsys.readouterr().out
