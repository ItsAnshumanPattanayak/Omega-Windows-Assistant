"""Path resolution utilities for the Omega source layout."""

from __future__ import annotations

from pathlib import Path


def project_root() -> Path:
    """Return the repository root without creating any directories."""
    return Path(__file__).resolve().parents[3]


def source_root() -> Path:
    """Return the source directory without creating any directories."""
    return project_root() / "src"


def config_dir() -> Path:
    """Return the project configuration directory without creating it."""
    return project_root() / "config"


def data_dir() -> Path:
    """Return the project runtime data directory without creating it."""
    return project_root() / "data"


def log_dir() -> Path:
    """Return the log directory without creating it."""
    return data_dir() / "logs"


def docs_dir() -> Path:
    """Return the documentation directory without creating it."""
    return project_root() / "docs"


def ensure_runtime_directories() -> None:
    """Create the directories used for runtime-generated data."""
    directories = (
        data_dir(),
        data_dir() / "action_backups",
        data_dir() / "command_history",
        log_dir(),
    )
    for directory in directories:
        directory.mkdir(parents=True, exist_ok=True)
