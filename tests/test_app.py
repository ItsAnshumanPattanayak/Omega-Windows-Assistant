"""Tests for Phase 0 application initialization and entry points."""

from omega.__main__ import main
from omega.app import OmegaApplication


def test_application_initializes_and_runs() -> None:
    app = OmegaApplication()

    assert app.settings.application_name == "Omega"
    assert app.run() is None


def test_main_returns_zero_when_application_runs(monkeypatch) -> None:
    class SuccessfulApplication:
        def run(self) -> None:
            return None

    monkeypatch.setattr("omega.__main__.OmegaApplication", SuccessfulApplication)

    assert main() == 0


def test_main_returns_nonzero_for_initialization_failure(monkeypatch, capsys) -> None:
    class FailingApplication:
        def __init__(self) -> None:
            from omega.core.exceptions import InitializationError

            raise InitializationError("test failure")

    monkeypatch.setattr("omega.__main__.OmegaApplication", FailingApplication)

    assert main() == 1
    assert "Omega initialization failed: test failure" in capsys.readouterr().err
