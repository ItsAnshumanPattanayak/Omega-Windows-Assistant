"""Omega SQLite schema foundation."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime

from omega.core.exceptions import DatabaseSchemaError

LATEST_SCHEMA_VERSION = 1
BASELINE_MIGRATION_NAME = "phase_9a_database_foundation"

CREATE_MIGRATIONS_TABLE = """
CREATE TABLE IF NOT EXISTS schema_migrations (
    version INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    applied_at TEXT NOT NULL
)
"""


def utc_timestamp() -> str:
    """Return a portable UTC timestamp."""

    return datetime.now(UTC).isoformat()


def ensure_migrations_table(
    connection: sqlite3.Connection,
) -> None:
    """Create the schema migration table."""

    try:
        connection.execute(CREATE_MIGRATIONS_TABLE)
    except sqlite3.Error as error:
        raise DatabaseSchemaError(
            "Omega could not create the " "schema migration table."
        ) from error


def get_schema_version(
    connection: sqlite3.Connection,
) -> int:
    """Return the latest applied schema version."""

    try:
        ensure_migrations_table(connection)

        row = connection.execute(
            """
            SELECT COALESCE(MAX(version), 0)
            FROM schema_migrations
            """
        ).fetchone()

        if row is None:
            return 0

        return int(row[0])
    except sqlite3.Error as error:
        raise DatabaseSchemaError(
            "Omega could not read the " "database schema version."
        ) from error


def apply_baseline_schema(
    connection: sqlite3.Connection,
) -> None:
    """Apply the Phase 9A baseline schema."""

    ensure_migrations_table(connection)


def initialize_schema(
    connection: sqlite3.Connection,
) -> int:
    """Initialize the database schema transactionally."""

    try:
        with connection:
            apply_baseline_schema(connection)

            connection.execute(
                """
                INSERT OR IGNORE INTO schema_migrations (
                    version,
                    name,
                    applied_at
                )
                VALUES (?, ?, ?)
                """,
                (
                    LATEST_SCHEMA_VERSION,
                    BASELINE_MIGRATION_NAME,
                    utc_timestamp(),
                ),
            )

        return get_schema_version(connection)
    except (
        sqlite3.Error,
        DatabaseSchemaError,
    ) as error:
        if isinstance(
            error,
            DatabaseSchemaError,
        ):
            raise

        raise DatabaseSchemaError(
            "Omega could not initialize " "the database schema."
        ) from error
