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
safety: {}
applications: {}
files: {}
"""


def test_load_settings_applies_sensible_defaults() -> None:
    with TemporaryDirectory(dir=Path.cwd() / "data") as temporary_directory:
        config_path = Path(temporary_directory) / "app_config.yaml"
        config_path.write_text(_valid_config(), encoding="utf-8")

        settings = load_settings(config_path)

        assert settings.application_name == "Omega"
        assert settings.assistant["activation_phrase"] == "Hello Omega"
        assert settings.logging["file_enabled"] is True
        assert settings.applications["allow_force_close"] is False
        assert settings.files["default_location"] == "desktop"
        assert settings.files["allow_absolute_paths"] is False


def test_missing_required_section_raises_configuration_error() -> None:
    with TemporaryDirectory(dir=Path.cwd() / "data") as temporary_directory:
        config_path = Path(temporary_directory) / "app_config.yaml"
        config_path.write_text("application: {}\nuser: {}\n", encoding="utf-8")

        with pytest.raises(ConfigurationError, match="missing required section"):
            load_settings(config_path)


def test_invalid_yaml_raises_configuration_error() -> None:
    with TemporaryDirectory(dir=Path.cwd() / "data") as temporary_directory:
        config_path = Path(temporary_directory) / "app_config.yaml"
        config_path.write_text("application: [unterminated\n", encoding="utf-8")

        with pytest.raises(ConfigurationError, match="Could not read configuration"):
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
def test_unsafe_file_settings_are_rejected(files: str) -> None:
    config = _valid_config().replace("files: {}", f"files:\n  {files}")
    with TemporaryDirectory(dir=Path.cwd() / "data") as temporary_directory:
        config_path = Path(temporary_directory) / "app_config.yaml"
        config_path.write_text(config, encoding="utf-8")
        with pytest.raises(ConfigurationError):
            load_settings(config_path)
