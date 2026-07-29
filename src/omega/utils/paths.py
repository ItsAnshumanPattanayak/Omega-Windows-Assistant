"""Source and frozen-application path resolution without import-time writes."""

from __future__ import annotations

import os
import sys
from collections.abc import Mapping
from pathlib import Path


def is_packaged() -> bool:
    """Return whether Omega is running from a freezer-provided executable."""

    return bool(getattr(sys, "frozen", False))


def resource_root() -> Path:
    """Return the read-only source or packaged resource root."""

    if is_packaged():
        bundle_root = getattr(sys, "_MEIPASS", None)
        selected = Path(bundle_root) if bundle_root else Path(sys.executable).parent
        return selected.resolve(strict=False)
    return Path(__file__).resolve().parents[3]


def project_root() -> Path:
    """Return the source repository or packaged resource root."""

    return resource_root()


def application_dir() -> Path:
    """Return the directory containing application files or the source root."""

    if is_packaged():
        return Path(sys.executable).resolve(strict=False).parent
    return project_root()


def source_root() -> Path:
    """Return the source directory without creating any directories."""

    return project_root() / "src"


def config_dir() -> Path:
    """Return the project configuration directory without creating it."""

    return project_root() / "config"


def data_dir(*, environment: Mapping[str, str] | None = None) -> Path:
    """Return the user-writable runtime root without creating it."""

    if is_packaged():
        values = os.environ if environment is None else environment
        explicit = values.get("OMEGA_DATA_DIR")
        if explicit:
            candidate = Path(explicit).expanduser()
            if not candidate.is_absolute():
                raise ValueError("OMEGA_DATA_DIR must be an absolute path.")
            return candidate.resolve(strict=False)
        local = values.get("LOCALAPPDATA")
        base = (
            Path(local)
            if local and Path(local).is_absolute()
            else (Path.home() / "AppData" / "Local")
        )
        return base.resolve(strict=False) / "Omega"
    return project_root() / "data"


def database_dir() -> Path:
    """Return the database directory without creating it."""

    return data_dir() / "database"


def log_dir() -> Path:
    """Return the log directory without creating it."""

    return data_dir() / "logs"


def docs_dir() -> Path:
    """Return the documentation directory without creating it."""

    return project_root() / "docs"


def user_config_dir() -> Path:
    """Return the user-owned configuration directory."""

    return data_dir() / "config"


def user_config_path() -> Path:
    """Return the user-owned configuration file path."""

    return user_config_dir() / "app_config.yaml"


def screenshot_dir() -> Path:
    """Return managed screenshot storage."""

    return data_dir() / "screenshots"


def plugin_dir() -> Path:
    """Return managed user-plugin storage."""

    return data_dir() / "plugins"


def ensure_runtime_directories() -> None:
    """Create only directories used for runtime-generated data."""

    directories = (
        data_dir(),
        data_dir() / "action_backups",
        data_dir() / "command_history",
        database_dir(),
        log_dir(),
        user_config_dir(),
        screenshot_dir(),
        plugin_dir(),
        data_dir() / "knowledge",
        data_dir() / "productivity",
        data_dir() / "temporary",
    )

    for directory in directories:
        directory.mkdir(
            parents=True,
            exist_ok=True,
        )
