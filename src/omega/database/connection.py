"""Safe SQLite connection creation."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from omega.core.exceptions import (
    DatabaseConnectionError,
)
from omega.database.configuration import (
    DatabaseConfiguration,
)


class DatabaseConnectionFactory:
    """Create consistently configured SQLite connections."""

    def __init__(
        self,
        configuration: DatabaseConfiguration,
        *,
        database_path: Path | None = None,
    ) -> None:
        self.configuration = configuration
        self.database_path = (
            database_path if database_path is not None else configuration.resolve_path()
        )

    def connect(
        self,
    ) -> sqlite3.Connection:
        """Open and configure one SQLite connection."""

        if not self.configuration.enabled:
            raise DatabaseConnectionError("The Omega database is disabled.")

        try:
            self.database_path.parent.mkdir(
                parents=True,
                exist_ok=True,
            )

            connection = sqlite3.connect(
                self.database_path,
                timeout=(self.configuration.busy_timeout_ms / 1_000),
            )

            connection.row_factory = sqlite3.Row

            self._configure(connection)

            return connection
        except (
            OSError,
            sqlite3.Error,
        ) as error:
            raise DatabaseConnectionError(
                "Omega could not open its local database."
            ) from error

    def _configure(
        self,
        connection: sqlite3.Connection,
    ) -> None:
        """Apply mandatory SQLite connection settings."""

        try:
            connection.execute("PRAGMA foreign_keys = ON")
            connection.execute(
                "PRAGMA busy_timeout = " f"{self.configuration.busy_timeout_ms}"
            )
            connection.execute(
                "PRAGMA journal_mode = " f"{self.configuration.journal_mode}"
            )
            connection.execute(
                "PRAGMA synchronous = " f"{self.configuration.synchronous}"
            )

            foreign_keys = connection.execute("PRAGMA foreign_keys").fetchone()

            if foreign_keys is None or int(foreign_keys[0]) != 1:
                raise DatabaseConnectionError(
                    "SQLite foreign-key enforcement " "could not be enabled."
                )
        except sqlite3.Error as error:
            connection.close()

            raise DatabaseConnectionError(
                "Omega could not configure its " "SQLite connection."
            ) from error
