"""Safe, lightweight YAML settings loading."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from omega.browser.configuration import BrowserConfiguration
from omega.core.exceptions import ConfigurationError
from omega.database.configuration import DatabaseConfiguration
from omega.system.configuration import SystemConfiguration
from omega.utils.constants import (
    APP_CONFIG_FILENAME,
    APP_NAME,
    APP_VERSION,
    DEFAULT_ACTIVATION_PHRASE,
    DEFAULT_SHUTDOWN_PHRASE,
)
from omega.utils.paths import config_dir, data_dir
from omega.voice.configuration import VoiceConfiguration

REQUIRED_SECTIONS = frozenset(
    {
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
    """Validated configuration values used by Omega."""

    application: Mapping[str, Any]
    user: Mapping[str, Any]
    assistant: Mapping[str, Any]
    logging: Mapping[str, Any]
    database: Mapping[str, Any]
    safety: Mapping[str, Any]
    applications: Mapping[str, Any]
    files: Mapping[str, Any]
    folders: Mapping[str, Any]
    recovery: Mapping[str, Any]
    history: Mapping[str, Any]
    voice: Mapping[str, Any]
    browser: Mapping[str, Any]
    system: Mapping[str, Any]

    @property
    def application_name(self) -> str:
        """Return the configured application name."""

        return str(
            self.application.get(
                "name",
                APP_NAME,
            )
        )

    @property
    def application_version(self) -> str:
        """Return the configured application version."""

        return str(
            self.application.get(
                "version",
                APP_VERSION,
            )
        )

    @property
    def database_configuration(self) -> DatabaseConfiguration:
        """Return the validated database configuration."""

        return DatabaseConfiguration.from_mapping(self.database)

    @property
    def voice_configuration(self) -> VoiceConfiguration:
        """Return strict optional voice settings without initializing audio."""

        return VoiceConfiguration.from_mapping(
            self.voice,
            wake_phrase=str(self.assistant["activation_phrase"]),
            shutdown_phrase=str(self.assistant["shutdown_phrase"]),
            model_root=data_dir() / "voice_models",
        )

    @property
    def browser_configuration(self) -> BrowserConfiguration:
        """Return strict browser policy without initializing a backend."""

        return BrowserConfiguration.from_mapping(self.browser)

    @property
    def system_configuration(self) -> SystemConfiguration:
        """Return strict system policy without querying the host."""

        return SystemConfiguration.from_mapping(self.system)


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
        "database": {
            "enabled": True,
            "filename": "omega.db",
            "busy_timeout_ms": 5_000,
            "journal_mode": "WAL",
            "synchronous": "NORMAL",
            "foreign_keys": True,
        },
        "safety": {
            "allow_administrator_operations": False,
            "allow_arbitrary_shell_commands": False,
            "permanent_deletion_enabled": False,
            "default_decision": "deny",
            "confirmation_timeout_seconds": 30,
            "maximum_confirmation_attempts": 3,
            "allow_force_close": False,
            "allow_absolute_paths": False,
            "allow_network_paths": False,
            "allow_device_paths": False,
            "allow_destination_replace": False,
            "allow_folder_merge": False,
            "allow_cross_volume_destructive_move": False,
        },
        "applications": {
            "launch_verification_timeout_seconds": 5,
            "graceful_close_timeout_seconds": 5,
            "force_close_timeout_seconds": 3,
            "allow_force_close": False,
        },
        "files": {
            "default_location": "desktop",
            "maximum_read_size_bytes": 1_048_576,
            "maximum_display_characters": 10_000,
            "maximum_write_size_bytes": 1_048_576,
            "maximum_resulting_file_size_bytes": 5_242_880,
            "search_max_depth": 5,
            "search_max_results": 50,
            "allow_absolute_paths": False,
            "allow_permanent_deletion": False,
        },
        "folders": {
            "default_location": "desktop",
            "maximum_listing_items": 100,
            "maximum_scan_depth": 10,
            "maximum_scan_items": 10_000,
            "maximum_scan_bytes": 10_737_418_240,
            "maximum_copy_depth": 20,
            "maximum_copy_items": 10_000,
            "maximum_copy_bytes": 5_368_709_120,
            "search_max_depth": 6,
            "search_max_results": 50,
            "allow_folder_merge": False,
            "allow_destination_replace": False,
            "allow_permanent_deletion": False,
            "allow_cross_volume_move": False,
        },
        "recovery": {
            "enabled": True,
            "allow_permanent_deletion": False,
            "require_confirmation_for_recycle": True,
            "require_confirmation_for_restore": True,
            "undo_timeout_seconds": 300,
            "maximum_undo_records": 20,
            "maximum_recycle_size_bytes": 5_368_709_120,
            "persist_undo_records": False,
        },
        "history": {
            "enabled": True,
            "persistence_enabled": True,
            "default_limit": 20,
            "maximum_limit": 100,
            "maximum_export_bytes": 1_048_576,
            "preserve_active_undo_records": True,
        },
        "voice": {
            "enabled": False,
            "offline_recognition_enabled": True,
            "model_path": None,
            "microphone_device": None,
            "sample_rate_hz": 16_000,
            "audio_block_size": 4_000,
            "passive_listening_timeout_seconds": 1,
            "active_listening_timeout_seconds": 10,
            "active_session_timeout_seconds": 300,
            "maximum_transcript_characters": 1_000,
            "minimum_confidence": 0.5,
            "speak_responses": True,
            "speech_rate": 180,
            "speech_volume": 1.0,
            "voice_name": None,
            "confirmation_confidence_threshold": 0.85,
            "return_to_passive_after_session": True,
        },
        "browser": {
            "enabled": True,
            "preferred_browser": "edge",
            "automation_enabled": True,
            "allowed_schemes": ["https"],
            "allow_http": False,
            "allow_file_urls": False,
            "allow_localhost": False,
            "allow_private_networks": False,
            "allow_url_credentials": False,
            "allow_javascript_urls": False,
            "allow_data_urls": False,
            "allow_downloads": False,
            "allow_form_submission": False,
            "allow_sensitive_input": False,
            "allow_private_mode": False,
            "navigation_timeout_seconds": 20,
            "operation_timeout_seconds": 10,
            "maximum_open_tabs": 10,
            "maximum_url_characters": 2048,
            "maximum_page_title_characters": 300,
            "maximum_page_text_characters": 10_000,
            "maximum_search_query_characters": 500,
            "maximum_bookmark_name_characters": 100,
            "default_search_engine": "duckduckgo",
        },
        "system": {},
    }


def _validate_files(
    values: Mapping[str, Any],
) -> None:
    default_location = values.get("default_location")

    if default_location not in _FILE_LOCATIONS:
        raise ConfigurationError("files.default_location must be registered.")

    positive = (
        "maximum_read_size_bytes",
        "maximum_display_characters",
        "maximum_write_size_bytes",
        "maximum_resulting_file_size_bytes",
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

    if (
        isinstance(result_limit, bool)
        or not isinstance(result_limit, int)
        or result_limit > 500
    ):
        raise ConfigurationError("files.search_max_results must not exceed 500.")

    if values.get("allow_absolute_paths") is not False:
        raise ConfigurationError("Phase 5 requires absolute file paths to be disabled.")

    if values.get("allow_permanent_deletion") is not False:
        raise ConfigurationError("Phase 5 requires permanent deletion to be disabled.")


def _validate_folders(
    values: Mapping[str, Any],
) -> None:
    if values.get("default_location") not in _FILE_LOCATIONS:
        raise ConfigurationError("folders.default_location must be registered.")

    positive = (
        "maximum_listing_items",
        "maximum_scan_items",
        "maximum_scan_bytes",
        "maximum_copy_items",
        "maximum_copy_bytes",
        "search_max_results",
    )

    for key in positive:
        value = values.get(key)

        if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
            raise ConfigurationError(f"folders.{key} must be a positive integer.")

    for key in (
        "maximum_scan_depth",
        "maximum_copy_depth",
        "search_max_depth",
    ):
        value = values.get(key)

        if (
            isinstance(value, bool)
            or not isinstance(value, int)
            or not 0 <= value <= 50
        ):
            raise ConfigurationError(f"folders.{key} must be between 0 and 50.")

    if (
        values.get(
            "maximum_listing_items",
            0,
        )
        > 1_000
    ):
        raise ConfigurationError("folders.maximum_listing_items must not exceed 1000.")

    if (
        values.get(
            "search_max_results",
            0,
        )
        > 500
    ):
        raise ConfigurationError("folders.search_max_results must not exceed 500.")

    switches = (
        "allow_folder_merge",
        "allow_destination_replace",
        "allow_permanent_deletion",
        "allow_cross_volume_move",
    )

    if any(values.get(key) is not False for key in switches):
        raise ConfigurationError(
            "Unsafe Phase 6 folder-policy switches must be disabled."
        )


def _validate_database(
    values: Mapping[str, Any],
) -> None:
    DatabaseConfiguration.from_mapping(values)


def _validate_recovery(
    values: Mapping[str, Any],
) -> None:
    """Validate immutable Phase 8 recovery boundaries."""

    from omega.recovery.configuration import (
        RecoveryConfiguration,
    )

    RecoveryConfiguration.from_mapping(values)


def _validate_safety(
    values: Mapping[str, Any],
) -> None:
    """Enforce immutable Phase 7 boundaries."""

    disabled = (
        "allow_administrator_operations",
        "allow_arbitrary_shell_commands",
        "permanent_deletion_enabled",
        "allow_force_close",
        "allow_absolute_paths",
        "allow_network_paths",
        "allow_device_paths",
        "allow_destination_replace",
        "allow_folder_merge",
        "allow_cross_volume_destructive_move",
    )

    if any(values.get(name) is not False for name in disabled):
        raise ConfigurationError(
            "Phase 7 hard safety-boundary settings must remain disabled."
        )

    if values.get("default_decision") != "deny":
        raise ConfigurationError("safety.default_decision must be deny.")

    timeout = values.get("confirmation_timeout_seconds")
    if (
        isinstance(timeout, bool)
        or not isinstance(timeout, (int, float))
        or not 0 < timeout <= 300
    ):
        raise ConfigurationError(
            "safety.confirmation_timeout_seconds must be between 0 and 300."
        )

    attempts = values.get("maximum_confirmation_attempts")
    if (
        isinstance(attempts, bool)
        or not isinstance(attempts, int)
        or not 1 <= attempts <= 10
    ):
        raise ConfigurationError(
            "safety.maximum_confirmation_attempts must be between 1 and 10."
        )


def _validate_history(values: Mapping[str, Any]) -> None:
    allowed = {
        "enabled",
        "persistence_enabled",
        "default_limit",
        "maximum_limit",
        "maximum_export_bytes",
        "preserve_active_undo_records",
    }
    unknown = set(values).difference(allowed)
    if unknown:
        raise ConfigurationError(
            "Unknown history setting(s): " + ", ".join(sorted(unknown))
        )
    for key in ("enabled", "persistence_enabled", "preserve_active_undo_records"):
        if not isinstance(values.get(key), bool):
            raise ConfigurationError(f"history.{key} must be a boolean.")
    for key, maximum in (
        ("default_limit", 1000),
        ("maximum_limit", 1000),
        ("maximum_export_bytes", 50_000_000),
    ):
        value = values.get(key)
        if (
            isinstance(value, bool)
            or not isinstance(value, int)
            or not 1 <= value <= maximum
        ):
            raise ConfigurationError(f"history.{key} is outside its safe range.")
    if values["default_limit"] > values["maximum_limit"]:
        raise ConfigurationError(
            "history.default_limit must not exceed history.maximum_limit."
        )


def _merge_defaults(
    raw: Mapping[str, Any],
) -> dict[str, Mapping[str, Any]]:
    merged: dict[str, Mapping[str, Any]] = {}

    for section, values in _defaults().items():
        supplied = (
            raw.get(section, {})
            if section in {"voice", "browser", "system"}
            else raw[section]
        )

        if not isinstance(
            supplied,
            Mapping,
        ):
            message = f"Configuration section " f"'{section}' must be a mapping."
            raise ConfigurationError(message)

        merged[section] = {
            **values,
            **supplied,
        }

    return merged


def load_settings(
    config_path: Path | None = None,
) -> Settings:
    """Load and validate Omega's YAML configuration."""

    path = config_path or config_dir() / APP_CONFIG_FILENAME

    try:
        with path.open(
            "r",
            encoding="utf-8",
        ) as config_file:
            raw = yaml.safe_load(config_file)
    except FileNotFoundError as error:
        raise ConfigurationError(f"Configuration file was not found: {path}") from error
    except (OSError, yaml.YAMLError) as error:
        raise ConfigurationError(
            f"Could not read configuration file: {path}"
        ) from error

    if not isinstance(
        raw,
        Mapping,
    ):
        raise ConfigurationError("Configuration root must be a YAML mapping.")

    missing_sections = REQUIRED_SECTIONS.difference(raw)

    if missing_sections:
        missing = ", ".join(sorted(missing_sections))
        message = "Configuration is missing required " f"section(s): {missing}"
        raise ConfigurationError(message)

    values = _merge_defaults(raw)

    _validate_database(values["database"])
    _validate_safety(values["safety"])
    _validate_files(values["files"])
    _validate_folders(values["folders"])
    _validate_recovery(values["recovery"])
    _validate_history(values["history"])
    VoiceConfiguration.from_mapping(
        values["voice"],
        wake_phrase=str(values["assistant"]["activation_phrase"]),
        shutdown_phrase=str(values["assistant"]["shutdown_phrase"]),
        model_root=data_dir() / "voice_models",
    )
    BrowserConfiguration.from_mapping(values["browser"])
    SystemConfiguration.from_mapping(values["system"])

    return Settings(**values)
