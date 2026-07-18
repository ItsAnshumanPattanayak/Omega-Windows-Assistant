"""Safe, lightweight YAML settings loading."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from omega.core.exceptions import ConfigurationError
from omega.utils.constants import (
    APP_CONFIG_FILENAME,
    APP_NAME,
    APP_VERSION,
    DEFAULT_ACTIVATION_PHRASE,
    DEFAULT_SHUTDOWN_PHRASE,
)
from omega.utils.paths import config_dir

REQUIRED_SECTIONS = frozenset(
    {
        "application",
        "user",
        "assistant",
        "logging",
        "safety",
        "applications",
        "files",
    }
)

_FILE_LOCATIONS = frozenset(
    {
        "desktop",
        "documents",
        "downloads",
        "pictures",
        "music",
        "videos",
        "home",
        "current_directory",
    }
)


@dataclass(frozen=True)
class Settings:
    """Validated configuration values used by the Phase 0 application."""

    application: Mapping[str, Any]
    user: Mapping[str, Any]
    assistant: Mapping[str, Any]
    logging: Mapping[str, Any]
    safety: Mapping[str, Any]
    applications: Mapping[str, Any]
    files: Mapping[str, Any]

    @property
    def application_name(self) -> str:
        """Return the configured application name."""
        return str(self.application.get("name", APP_NAME))

    @property
    def application_version(self) -> str:
        """Return the configured application version."""
        return str(self.application.get("version", APP_VERSION))


def _defaults() -> dict[str, dict[str, Any]]:
    return {
        "application": {
            "name": APP_NAME,
            "version": APP_VERSION,
            "environment": "development",
        },
        "user": {},
        "assistant": {
            "activation_phrase": DEFAULT_ACTIVATION_PHRASE,
            "shutdown_phrase": DEFAULT_SHUTDOWN_PHRASE,
            "active_session_timeout_seconds": 300,
        },
        "logging": {
            "level": "INFO",
            "console_enabled": True,
            "file_enabled": True,
            "max_file_size_mb": 5,
            "backup_count": 3,
        },
        "safety": {
            "allow_administrator_operations": False,
            "allow_arbitrary_shell_commands": False,
            "permanent_deletion_enabled": False,
        },
        "applications": {
            "launch_verification_timeout_seconds": 5,
            "graceful_close_timeout_seconds": 5,
            "force_close_timeout_seconds": 3,
            "confirmation_timeout_seconds": 30,
            "allow_force_close": False,
        },
        "files": {
            "default_location": "desktop",
            "maximum_read_size_bytes": 1_048_576,
            "maximum_display_characters": 10_000,
            "maximum_write_size_bytes": 1_048_576,
            "maximum_resulting_file_size_bytes": 5_242_880,
            "confirmation_timeout_seconds": 30,
            "search_max_depth": 5,
            "search_max_results": 50,
            "allow_absolute_paths": False,
            "allow_permanent_deletion": False,
        },
    }


def _validate_files(values: Mapping[str, Any]) -> None:
    default_location = values.get("default_location")
    if default_location not in _FILE_LOCATIONS:
        raise ConfigurationError("files.default_location must be registered.")
    positive = (
        "maximum_read_size_bytes",
        "maximum_display_characters",
        "maximum_write_size_bytes",
        "maximum_resulting_file_size_bytes",
        "confirmation_timeout_seconds",
        "search_max_results",
    )
    for key in positive:
        value = values.get(key)
        if isinstance(value, bool) or not isinstance(value, (int, float)) or value <= 0:
            raise ConfigurationError(f"files.{key} must be positive.")
    depth = values.get("search_max_depth")
    if isinstance(depth, bool) or not isinstance(depth, int) or not 0 <= depth <= 20:
        raise ConfigurationError("files.search_max_depth must be between 0 and 20.")
    result_limit = values.get("search_max_results")
    if not isinstance(result_limit, int) or result_limit > 500:
        raise ConfigurationError("files.search_max_results must not exceed 500.")
    if values.get("allow_absolute_paths") is not False:
        raise ConfigurationError("Phase 5 requires absolute file paths to be disabled.")
    if values.get("allow_permanent_deletion") is not False:
        raise ConfigurationError("Phase 5 requires permanent deletion to be disabled.")


def _merge_defaults(raw: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    merged: dict[str, Mapping[str, Any]] = {}
    for section, values in _defaults().items():
        supplied = raw[section]
        if not isinstance(supplied, Mapping):
            message = f"Configuration section '{section}' must be a mapping."
            raise ConfigurationError(message)
        merged[section] = {**values, **supplied}
    return merged


def load_settings(config_path: Path | None = None) -> Settings:
    """Load and validate Omega's project-level YAML configuration."""
    path = config_path or config_dir() / APP_CONFIG_FILENAME
    try:
        with path.open("r", encoding="utf-8") as config_file:
            raw = yaml.safe_load(config_file)
    except FileNotFoundError as error:
        raise ConfigurationError(f"Configuration file was not found: {path}") from error
    except (OSError, yaml.YAMLError) as error:
        raise ConfigurationError(
            f"Could not read configuration file: {path}"
        ) from error

    if not isinstance(raw, Mapping):
        raise ConfigurationError("Configuration root must be a YAML mapping.")

    missing_sections = REQUIRED_SECTIONS.difference(raw)
    if missing_sections:
        missing = ", ".join(sorted(missing_sections))
        message = f"Configuration is missing required section(s): {missing}"
        raise ConfigurationError(message)

    values = _merge_defaults(raw)
    _validate_files(values["files"])
    return Settings(**values)
