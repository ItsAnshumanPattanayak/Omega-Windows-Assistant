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
"""


def test_load_settings_applies_sensible_defaults() -> None:
    with TemporaryDirectory(dir=Path.cwd() / "data") as temporary_directory:
        config_path = Path(temporary_directory) / "app_config.yaml"
        config_path.write_text(_valid_config(), encoding="utf-8")

        settings = load_settings(config_path)

        assert settings.application_name == "Omega"
        assert settings.assistant["activation_phrase"] == "Hello Omega"
        assert settings.logging["file_enabled"] is True


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
