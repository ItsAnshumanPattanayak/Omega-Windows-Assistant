import logging
import shutil
import sys
from pathlib import Path

import pytest

from omega.config import load_settings
from omega.core.exceptions import ConfigurationError
from omega.distribution.first_run import ensure_user_configuration, prepare_first_run
from omega.utils import paths
from omega.utils.logger import configure_logging


def _simulate_packaged(
    monkeypatch: pytest.MonkeyPatch, bundle: Path, runtime: Path
) -> None:
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(bundle), raising=False)
    monkeypatch.setenv("OMEGA_DATA_DIR", str(runtime))


def test_source_resource_and_runtime_paths_remain_repository_relative() -> None:
    assert not paths.is_packaged()
    assert paths.resource_root() == paths.project_root()
    assert paths.config_dir() == paths.project_root() / "config"
    assert paths.data_dir() == paths.project_root() / "data"


def test_packaged_paths_separate_resources_and_user_data(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    bundle = tmp_path / "bundle" / "_internal"
    runtime = tmp_path / "local" / "Omega"
    bundle.mkdir(parents=True)
    _simulate_packaged(monkeypatch, bundle, runtime)
    assert paths.resource_root() == bundle.resolve()
    assert paths.config_dir() == bundle.resolve() / "config"
    assert paths.data_dir() == runtime.resolve()
    assert paths.database_dir() == runtime.resolve() / "database"
    assert paths.log_dir() == runtime.resolve() / "logs"
    assert paths.screenshot_dir() == runtime.resolve() / "screenshots"
    assert paths.plugin_dir() == runtime.resolve() / "plugins"


def test_relative_packaged_data_override_is_rejected(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _simulate_packaged(monkeypatch, tmp_path, tmp_path / "runtime")
    with pytest.raises(ValueError, match="absolute"):
        paths.data_dir(environment={"OMEGA_DATA_DIR": "relative"})


def test_first_run_creates_config_once_and_preserves_changes(tmp_path: Path) -> None:
    source = tmp_path / "safe.yaml"
    destination = tmp_path / "runtime" / "config" / "app_config.yaml"
    source.write_text("application: {}\n", encoding="utf-8")
    path, created = ensure_user_configuration(
        default_path=source, destination=destination
    )
    assert path == destination and created
    destination.write_text(
        "application:\n  environment: customized\n", encoding="utf-8"
    )
    _, created_again = ensure_user_configuration(
        default_path=source, destination=destination
    )
    assert not created_again
    assert "customized" in destination.read_text(encoding="utf-8")


def test_packaged_settings_create_safe_user_config_without_source_writes(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    bundle = tmp_path / "bundle"
    resource_config = bundle / "config" / "app_config.yaml"
    resource_config.parent.mkdir(parents=True)
    shutil.copy2(Path("packaging/defaults/app_config.yaml"), resource_config)
    runtime = tmp_path / "runtime"
    _simulate_packaged(monkeypatch, bundle, runtime)
    settings = load_settings()
    assert settings.user["display_name"] == "User"
    assert not settings.voice_configuration.enabled
    assert (runtime / "config" / "app_config.yaml").is_file()
    assert (
        resource_config.read_bytes()
        == Path("packaging/defaults/app_config.yaml").read_bytes()
    )


def test_packaged_read_only_settings_do_not_create_user_config(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    bundle = tmp_path / "bundle"
    resource_config = bundle / "config" / "app_config.yaml"
    resource_config.parent.mkdir(parents=True)
    shutil.copy2(Path("packaging/defaults/app_config.yaml"), resource_config)
    runtime = tmp_path / "runtime"
    _simulate_packaged(monkeypatch, bundle, runtime)
    settings = load_settings(initialize_user_configuration=False)
    assert settings.application_name == "Omega"
    assert not runtime.exists()


def test_prepare_first_run_is_idempotent(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    source = Path("packaging/defaults/app_config.yaml")
    destination = tmp_path / "runtime" / "config" / "app_config.yaml"
    monkeypatch.setattr("omega.distribution.first_run.data_dir", lambda: tmp_path)
    monkeypatch.setattr(
        "omega.distribution.first_run.ensure_runtime_directories",
        lambda: destination.parent.mkdir(parents=True, exist_ok=True),
    )
    first = prepare_first_run(default_config_path=source, destination=destination)
    second = prepare_first_run(default_config_path=source, destination=destination)
    assert first.configuration_created
    assert not second.configuration_created


def test_invalid_packaged_configuration_remains_a_bounded_error(tmp_path: Path) -> None:
    invalid = tmp_path / "app_config.yaml"
    invalid.write_text("application: [invalid\n", encoding="utf-8")
    with pytest.raises(ConfigurationError, match="Could not read configuration"):
        load_settings(invalid)


def test_packaged_logging_uses_user_writable_directory(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    runtime = tmp_path / "runtime"
    _simulate_packaged(monkeypatch, tmp_path / "bundle", runtime)
    logger = logging.getLogger("omega")
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
        handler.close()
    configure_logging(console_enabled=False, log_directory=paths.log_dir())
    logger.info("packaged logging smoke")
    assert (runtime / "logs" / "omega.log").is_file()
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
        handler.close()
