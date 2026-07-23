"""Tests for safe configuration loading."""

from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from omega.config.settings import load_settings
from omega.core.exceptions import ConfigurationError


def _valid_config() -> str:
    return """\
application: {}
user: {}
assistant: {}
logging: {}
database: {}
safety: {}
applications: {}
files: {}
folders: {}
recovery: {}
history: {}
"""


def test_load_settings_applies_sensible_defaults() -> None:
    with TemporaryDirectory(dir=Path.cwd() / "data") as temporary_directory:
        config_path = Path(temporary_directory) / "app_config.yaml"

        config_path.write_text(
            _valid_config(),
            encoding="utf-8",
        )

        settings = load_settings(config_path)

        assert settings.application_name == "Omega"
        assert settings.assistant["activation_phrase"] == "Hello Omega"
        assert settings.logging["file_enabled"] is True
        assert settings.applications["allow_force_close"] is False
        assert settings.files["default_location"] == "desktop"
        assert settings.files["allow_absolute_paths"] is False
        assert settings.folders["maximum_listing_items"] == 100
        assert settings.folders["allow_permanent_deletion"] is False
        assert settings.safety["default_decision"] == "deny"
        assert settings.safety["maximum_confirmation_attempts"] == 3

        database = settings.database_configuration

        assert database.enabled
        assert database.filename == "omega.db"
        assert database.busy_timeout_ms == 5_000
        assert database.journal_mode == "WAL"
        assert database.synchronous == "NORMAL"
        assert database.foreign_keys

        assert settings.recovery["enabled"] is True
        assert settings.recovery["allow_permanent_deletion"] is False
        assert settings.recovery["require_confirmation_for_recycle"] is True
        assert settings.recovery["require_confirmation_for_restore"] is True
        assert settings.recovery["undo_timeout_seconds"] == 300
        assert settings.recovery["maximum_undo_records"] == 20
        assert settings.recovery["persist_undo_records"] is False
        assert settings.history["default_limit"] == 20


def test_missing_required_section_raises_configuration_error() -> None:
    with TemporaryDirectory(dir=Path.cwd() / "data") as temporary_directory:
        config_path = Path(temporary_directory) / "app_config.yaml"

        config_path.write_text(
            "application: {}\nuser: {}\n",
            encoding="utf-8",
        )

        with pytest.raises(
            ConfigurationError,
            match="missing required section",
        ):
            load_settings(config_path)


def test_invalid_yaml_raises_configuration_error() -> None:
    with TemporaryDirectory(dir=Path.cwd() / "data") as temporary_directory:
        config_path = Path(temporary_directory) / "app_config.yaml"

        config_path.write_text(
            "application: [unterminated\n",
            encoding="utf-8",
        )

        with pytest.raises(
            ConfigurationError,
            match="Could not read configuration",
        ):
            load_settings(config_path)


@pytest.mark.parametrize(
    "database",
    [
        "enabled: invalid",
        "filename: ../omega.db",
        "filename: omega.txt",
        "busy_timeout_ms: 0",
        "busy_timeout_ms: 60001",
        "journal_mode: invalid",
        "synchronous: invalid",
        "foreign_keys: false",
        "unknown_setting: true",
    ],
)
def test_unsafe_database_settings_are_rejected(
    database: str,
) -> None:
    config = _valid_config().replace(
        "database: {}",
        f"database:\n  {database}",
    )

    with TemporaryDirectory(dir=Path.cwd() / "data") as temporary_directory:
        config_path = Path(temporary_directory) / "app_config.yaml"

        config_path.write_text(
            config,
            encoding="utf-8",
        )

        with pytest.raises(ConfigurationError):
            load_settings(config_path)


@pytest.mark.parametrize(
    "files",
    [
        "default_location: system32",
        "maximum_read_size_bytes: 0",
        "search_max_depth: 21",
        "search_max_results: 501",
        "allow_absolute_paths: true",
        "allow_permanent_deletion: true",
    ],
)
def test_unsafe_file_settings_are_rejected(
    files: str,
) -> None:
    config = _valid_config().replace(
        "files: {}",
        f"files:\n  {files}",
    )

    with TemporaryDirectory(dir=Path.cwd() / "data") as temporary_directory:
        config_path = Path(temporary_directory) / "app_config.yaml"

        config_path.write_text(
            config,
            encoding="utf-8",
        )

        with pytest.raises(ConfigurationError):
            load_settings(config_path)


@pytest.mark.parametrize(
    "folders",
    [
        "default_location: system32",
        "maximum_listing_items: 0",
        "maximum_scan_depth: 51",
        "maximum_copy_items: -1",
        "search_max_results: 501",
        "allow_folder_merge: true",
        "allow_destination_replace: true",
        "allow_permanent_deletion: true",
        "allow_cross_volume_move: true",
    ],
)
def test_unsafe_folder_settings_are_rejected(
    folders: str,
) -> None:
    config = _valid_config().replace(
        "folders: {}",
        f"folders:\n  {folders}",
    )

    with TemporaryDirectory(dir=Path.cwd() / "data") as temporary_directory:
        config_path = Path(temporary_directory) / "app_config.yaml"

        config_path.write_text(
            config,
            encoding="utf-8",
        )

        with pytest.raises(ConfigurationError):
            load_settings(config_path)


@pytest.mark.parametrize(
    "safety",
    [
        "default_decision: allow",
        "allow_administrator_operations: true",
        "allow_arbitrary_shell_commands: true",
        "permanent_deletion_enabled: true",
        "allow_absolute_paths: true",
        "allow_network_paths: true",
        "allow_device_paths: true",
        "allow_force_close: true",
        "allow_destination_replace: true",
        "allow_folder_merge: true",
        "allow_cross_volume_destructive_move: true",
        "confirmation_timeout_seconds: -1",
        "confirmation_timeout_seconds: 301",
        "maximum_confirmation_attempts: 0",
        "maximum_confirmation_attempts: 11",
    ],
)
def test_unsafe_central_safety_settings_are_rejected(
    safety: str,
) -> None:
    config = _valid_config().replace(
        "safety: {}",
        f"safety:\n  {safety}",
    )

    with TemporaryDirectory(dir=Path.cwd() / "data") as temporary_directory:
        config_path = Path(temporary_directory) / "app_config.yaml"

        config_path.write_text(
            config,
            encoding="utf-8",
        )

        with pytest.raises(ConfigurationError):
            load_settings(config_path)


@pytest.mark.parametrize(
    "recovery",
    [
        "allow_permanent_deletion: true",
        "undo_timeout_seconds: 0",
        "undo_timeout_seconds: 3601",
        "maximum_undo_records: 0",
        "maximum_undo_records: 101",
        "maximum_recycle_size_bytes: 0",
        "maximum_recycle_size_bytes: 53687091201",
    ],
)
def test_unsafe_recovery_settings_are_rejected(
    recovery: str,
) -> None:
    config = _valid_config().replace(
        "recovery: {}",
        f"recovery:\n  {recovery}",
    )

    with TemporaryDirectory(dir=Path.cwd() / "data") as temporary_directory:
        config_path = Path(temporary_directory) / "app_config.yaml"

        config_path.write_text(
            config,
            encoding="utf-8",
        )

        with pytest.raises(ConfigurationError):
            load_settings(config_path)


def test_unknown_recovery_setting_is_rejected() -> None:
    config = _valid_config().replace(
        "recovery: {}",
        "recovery:\n  unknown_switch: true",
    )

    with TemporaryDirectory(dir=Path.cwd() / "data") as temporary_directory:
        config_path = Path(temporary_directory) / "app_config.yaml"

        config_path.write_text(
            config,
            encoding="utf-8",
        )

        with pytest.raises(
            ConfigurationError,
            match="Unknown recovery",
        ):
            load_settings(config_path)


@pytest.mark.parametrize(
    "section",
    [
        "application",
        "user",
        "assistant",
        "logging",
        "database",
        "safety",
        "applications",
        "files",
        "folders",
        "recovery",
        "history",
    ],
)
def test_configuration_sections_must_be_mappings(
    section: str,
) -> None:
    config = _valid_config().replace(
        f"{section}: {{}}",
        f"{section}: invalid",
    )

    with TemporaryDirectory(dir=Path.cwd() / "data") as temporary_directory:
        config_path = Path(temporary_directory) / "app_config.yaml"

        config_path.write_text(
            config,
            encoding="utf-8",
        )

        with pytest.raises(
            ConfigurationError,
            match="must be a mapping",
        ):
            load_settings(config_path)
