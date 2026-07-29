import sys
import tomllib
from pathlib import Path

import pytest

from omega.__main__ import main
from omega.config import load_settings
from omega.database import (
    DatabaseConfiguration,
    DatabaseConnectionFactory,
    MigrationRunner,
    get_schema_version,
)
from omega.distribution import APPLICATION_METADATA, selected_arguments
from omega.security.diagnostics import FindingSeverity, SecurityDiagnostics
from omega.utils import paths
from omega.utils.constants import APP_VERSION


def test_version_metadata_is_consistent(capsys: pytest.CaptureFixture[str]) -> None:
    project = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))
    defaults = load_settings(Path("packaging/defaults/app_config.yaml"))
    assert APPLICATION_METADATA.version == APP_VERSION
    assert project["project"]["version"] == APP_VERSION
    assert defaults.application_version == APP_VERSION
    assert main(["--version"]) == 0
    assert capsys.readouterr().out.strip() == f"omega-windows-assistant {APP_VERSION}"


def test_version_does_not_import_application_graph() -> None:
    sys.modules.pop("omega.app", None)
    assert main(["--version"]) == 0
    assert "omega.app" not in sys.modules


def test_frozen_cli_and_gui_entrypoint_defaults() -> None:
    assert selected_arguments(Path("Omega.exe"), ()) == ["--gui"]
    assert selected_arguments(Path("OmegaCLI.exe"), ()) == []
    assert selected_arguments(Path("Omega.exe"), ("--version",)) == ["--version"]


def test_packaged_database_initializes_and_migrates_in_user_data(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(paths, "is_packaged", lambda: True)
    monkeypatch.setenv("OMEGA_DATA_DIR", str(tmp_path / "runtime"))
    database_path = DatabaseConfiguration().resolve_path()
    factory = DatabaseConnectionFactory(
        DatabaseConfiguration(), database_path=database_path
    )
    first_version = MigrationRunner(factory).migrate()
    second_version = MigrationRunner(factory).migrate()
    assert first_version == second_version
    assert database_path.parent == tmp_path / "runtime" / "database"
    with factory.connect() as connection:
        assert get_schema_version(connection) == first_version


def test_packaged_defaults_leave_optional_integrations_unconfigured() -> None:
    settings = load_settings(Path("packaging/defaults/app_config.yaml"))
    assert not settings.voice_configuration.enabled
    assert not settings.ai_configuration.enabled
    assert not settings.email_configuration.enabled
    assert not settings.calendar_configuration.enabled
    assert not settings.plugin_configuration.load_user_plugins


def test_packaged_security_diagnostic_reports_build_time_scan(tmp_path: Path) -> None:
    settings = load_settings(Path("packaging/defaults/app_config.yaml"))
    report = SecurityDiagnostics(
        settings.security_configuration, repository_root=tmp_path / "bundle"
    ).run(settings)
    packaged = [
        item
        for item in report.findings
        if item.code == "PACKAGED_SOURCE_SCAN_UNAVAILABLE"
    ]
    assert report.passed
    assert len(packaged) == 1
    assert packaged[0].severity is FindingSeverity.INFORMATION
