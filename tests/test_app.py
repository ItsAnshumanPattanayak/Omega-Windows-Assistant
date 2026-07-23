"""Tests for Phase 0 application initialization and entry points."""

from pathlib import Path

from omega.__main__ import main
from omega.app import OmegaApplication
from omega.database import SqliteRecoveryRecordStore


def test_application_initializes_and_runs() -> None:
    app = OmegaApplication()

    assert app.settings.application_name == "Omega"
    assert (
        app.run(input_func=lambda _: "Shut down Omega", output_func=lambda _: None) == 0
    )


def test_application_explicitly_composes_phase10_database(tmp_path: Path) -> None:
    database_path = tmp_path / "omega.db"
    assert not database_path.exists()

    app = OmegaApplication(database_path=database_path)

    assert database_path.exists()
    assert app.command_repository.connection_factory is app.database_factory
    assert app.action_repository.connection_factory is app.database_factory
    assert app.runtime_settings_repository.connection_factory is app.database_factory
    assert isinstance(app.recovery_registry.store, SqliteRecoveryRecordStore)
    assert app.history_service.connection_factory is app.database_factory


def test_main_returns_zero_when_application_runs(monkeypatch) -> None:
    class SuccessfulApplication:
        def run(self) -> int:
            return 0

    monkeypatch.setattr("omega.__main__.OmegaApplication", SuccessfulApplication)

    assert main([]) == 0


def test_main_returns_nonzero_for_initialization_failure(monkeypatch, capsys) -> None:
    class FailingApplication:
        def __init__(self) -> None:
            from omega.core.exceptions import InitializationError

            raise InitializationError("test failure")

    monkeypatch.setattr("omega.__main__.OmegaApplication", FailingApplication)

    assert main([]) == 1
    assert "Omega initialization failed: test failure" in capsys.readouterr().err
