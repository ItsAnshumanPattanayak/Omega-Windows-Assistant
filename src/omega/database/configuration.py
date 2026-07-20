"""Validated SQLite database configuration."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from omega.core.exceptions import (
    DatabaseConfigurationError,
)
from omega.utils.paths import database_dir

_ALLOWED_KEYS = frozenset(
    {
        "enabled",
        "filename",
        "busy_timeout_ms",
        "journal_mode",
        "synchronous",
        "foreign_keys",
    }
)

_ALLOWED_SUFFIXES = frozenset(
    {
        ".db",
        ".sqlite",
        ".sqlite3",
    }
)

_ALLOWED_JOURNAL_MODES = frozenset(
    {
        "DELETE",
        "TRUNCATE",
        "PERSIST",
        "MEMORY",
        "WAL",
    }
)

_ALLOWED_SYNCHRONOUS_MODES = frozenset(
    {
        "OFF",
        "NORMAL",
        "FULL",
        "EXTRA",
    }
)


@dataclass(frozen=True)
class DatabaseConfiguration:
    """Immutable and validated SQLite configuration."""

    enabled: bool = True
    filename: str = "omega.db"
    busy_timeout_ms: int = 5_000
    journal_mode: str = "WAL"
    synchronous: str = "NORMAL"
    foreign_keys: bool = True

    @classmethod
    def from_mapping(
        cls,
        values: Mapping[str, Any],
    ) -> DatabaseConfiguration:
        """Build configuration from a validated mapping."""

        unknown = set(values).difference(_ALLOWED_KEYS)

        if unknown:
            names = ", ".join(sorted(unknown))
            raise DatabaseConfigurationError(f"Unknown database setting(s): {names}")

        enabled = values.get(
            "enabled",
            True,
        )
        filename = values.get(
            "filename",
            "omega.db",
        )
        busy_timeout_ms = values.get(
            "busy_timeout_ms",
            5_000,
        )
        journal_mode = values.get(
            "journal_mode",
            "WAL",
        )
        synchronous = values.get(
            "synchronous",
            "NORMAL",
        )
        foreign_keys = values.get(
            "foreign_keys",
            True,
        )

        if not isinstance(
            enabled,
            bool,
        ):
            raise DatabaseConfigurationError("database.enabled must be a boolean.")

        if not isinstance(filename, str) or not filename.strip():
            raise DatabaseConfigurationError(
                "database.filename must be a non-empty string."
            )

        normalized_filename = filename.strip()
        candidate = Path(normalized_filename)

        if (
            candidate.is_absolute()
            or candidate.name != normalized_filename
            or "/" in normalized_filename
            or "\\" in normalized_filename
        ):
            raise DatabaseConfigurationError(
                "database.filename must contain only a file name."
            )

        if candidate.suffix.casefold() not in _ALLOWED_SUFFIXES:
            raise DatabaseConfigurationError(
                "database.filename must use .db, " ".sqlite, or .sqlite3."
            )

        if (
            isinstance(busy_timeout_ms, bool)
            or not isinstance(
                busy_timeout_ms,
                int,
            )
            or not 100 <= busy_timeout_ms <= 60_000
        ):
            raise DatabaseConfigurationError(
                "database.busy_timeout_ms must be " "between 100 and 60000."
            )

        if not isinstance(
            journal_mode,
            str,
        ):
            raise DatabaseConfigurationError("database.journal_mode must be a string.")

        normalized_journal_mode = journal_mode.strip().upper()

        if normalized_journal_mode not in _ALLOWED_JOURNAL_MODES:
            raise DatabaseConfigurationError("database.journal_mode is not supported.")

        if not isinstance(
            synchronous,
            str,
        ):
            raise DatabaseConfigurationError("database.synchronous must be a string.")

        normalized_synchronous = synchronous.strip().upper()

        if normalized_synchronous not in _ALLOWED_SYNCHRONOUS_MODES:
            raise DatabaseConfigurationError("database.synchronous is not supported.")

        if foreign_keys is not True:
            raise DatabaseConfigurationError(
                "database.foreign_keys must remain enabled."
            )

        return cls(
            enabled=enabled,
            filename=normalized_filename,
            busy_timeout_ms=busy_timeout_ms,
            journal_mode=normalized_journal_mode,
            synchronous=normalized_synchronous,
            foreign_keys=foreign_keys,
        )

    def resolve_path(
        self,
        directory: Path | None = None,
    ) -> Path:
        """Return the database file path without creating it."""

        selected_directory = directory if directory is not None else database_dir()

        return selected_directory / self.filename
