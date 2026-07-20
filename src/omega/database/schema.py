"""Omega SQLite schema definitions and initialization."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime

from omega.core.exceptions import DatabaseSchemaError

BASELINE_SCHEMA_VERSION = 1
COMMAND_SCHEMA_VERSION = 2
ACTION_SCHEMA_VERSION = 3
LATEST_SCHEMA_VERSION = ACTION_SCHEMA_VERSION

BASELINE_MIGRATION_NAME = "phase_9a_database_foundation"
COMMAND_MIGRATION_NAME = "phase_9b_command_repository"
ACTION_MIGRATION_NAME = "phase_9c_action_repository"

CREATE_MIGRATIONS_TABLE = """
CREATE TABLE IF NOT EXISTS schema_migrations (
    version INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    applied_at TEXT NOT NULL
)
"""

CREATE_COMMANDS_TABLE = """
CREATE TABLE IF NOT EXISTS commands (
    command_id TEXT PRIMARY KEY,
    original_text TEXT NOT NULL,
    normalized_text TEXT,
    intent TEXT NOT NULL,
    entities_json TEXT NOT NULL,
    confidence REAL NOT NULL,
    received_at TEXT NOT NULL,
    source TEXT NOT NULL,
    session_id TEXT,
    metadata_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    CHECK (length(trim(original_text)) > 0),
    CHECK (
        normalized_text IS NULL
        OR length(trim(normalized_text)) > 0
    ),
    CHECK (confidence >= 0.0 AND confidence <= 1.0)
)
"""

CREATE_COMMANDS_RECEIVED_AT_INDEX = """
CREATE INDEX IF NOT EXISTS idx_commands_received_at
ON commands(received_at DESC)
"""

CREATE_COMMANDS_SESSION_INDEX = """
CREATE INDEX IF NOT EXISTS idx_commands_session_id
ON commands(session_id)
"""

CREATE_COMMANDS_INTENT_INDEX = """
CREATE INDEX IF NOT EXISTS idx_commands_intent
ON commands(intent)
"""

CREATE_ACTIONS_TABLE = """
CREATE TABLE IF NOT EXISTS actions (
    action_id TEXT PRIMARY KEY,
    command_id TEXT NOT NULL,
    intent TEXT NOT NULL,
    parameters_json TEXT NOT NULL,
    risk_level TEXT NOT NULL,
    status TEXT NOT NULL,
    permission_decision TEXT NOT NULL,
    confirmation_status TEXT NOT NULL,
    requires_confirmation INTEGER NOT NULL,
    dependencies_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    started_at TEXT,
    completed_at TEXT,
    metadata_json TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (command_id)
        REFERENCES commands(command_id)
        ON UPDATE CASCADE
        ON DELETE CASCADE,
    CHECK (requires_confirmation IN (0, 1))
)
"""

CREATE_ACTION_RESULTS_TABLE = """
CREATE TABLE IF NOT EXISTS action_results (
    action_id TEXT PRIMARY KEY,
    success INTEGER NOT NULL,
    status TEXT NOT NULL,
    message TEXT NOT NULL,
    user_message TEXT NOT NULL,
    data_json TEXT NOT NULL,
    error_json TEXT,
    started_at TEXT,
    completed_at TEXT,
    duration_ms INTEGER,
    metadata_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (action_id)
        REFERENCES actions(action_id)
        ON UPDATE CASCADE
        ON DELETE CASCADE,
    CHECK (success IN (0, 1)),
    CHECK (duration_ms IS NULL OR duration_ms >= 0),
    CHECK (length(trim(message)) > 0),
    CHECK (length(trim(user_message)) > 0)
)
"""

CREATE_ACTIONS_COMMAND_INDEX = """
CREATE INDEX IF NOT EXISTS idx_actions_command_id
ON actions(command_id)
"""

CREATE_ACTIONS_CREATED_AT_INDEX = """
CREATE INDEX IF NOT EXISTS idx_actions_created_at
ON actions(created_at DESC)
"""

CREATE_ACTIONS_STATUS_INDEX = """
CREATE INDEX IF NOT EXISTS idx_actions_status
ON actions(status)
"""

CREATE_ACTIONS_INTENT_INDEX = """
CREATE INDEX IF NOT EXISTS idx_actions_intent
ON actions(intent)
"""


def utc_timestamp() -> str:
    """Return an ISO-8601 UTC timestamp."""

    return datetime.now(UTC).isoformat()


def ensure_migrations_table(
    connection: sqlite3.Connection,
) -> None:
    """Create the schema-migration table."""

    try:
        connection.execute(CREATE_MIGRATIONS_TABLE)
    except sqlite3.Error as error:
        raise DatabaseSchemaError(
            "Omega could not create the schema migration table."
        ) from error


def get_schema_version(
    connection: sqlite3.Connection,
) -> int:
    """Return the highest applied schema version."""

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
            "Omega could not read the database schema version."
        ) from error


def apply_baseline_schema(
    connection: sqlite3.Connection,
) -> None:
    """Apply the Phase 9A baseline schema."""

    ensure_migrations_table(connection)


def apply_command_schema(
    connection: sqlite3.Connection,
) -> None:
    """Create the persistent command-history schema."""

    try:
        connection.execute(CREATE_COMMANDS_TABLE)
        connection.execute(CREATE_COMMANDS_RECEIVED_AT_INDEX)
        connection.execute(CREATE_COMMANDS_SESSION_INDEX)
        connection.execute(CREATE_COMMANDS_INTENT_INDEX)
    except sqlite3.Error as error:
        raise DatabaseSchemaError(
            "Omega could not create the command-history schema."
        ) from error


def apply_action_schema(
    connection: sqlite3.Connection,
) -> None:
    """Create the persistent action and result schema."""

    try:
        connection.execute(CREATE_ACTIONS_TABLE)
        connection.execute(CREATE_ACTION_RESULTS_TABLE)
        connection.execute(CREATE_ACTIONS_COMMAND_INDEX)
        connection.execute(CREATE_ACTIONS_CREATED_AT_INDEX)
        connection.execute(CREATE_ACTIONS_STATUS_INDEX)
        connection.execute(CREATE_ACTIONS_INTENT_INDEX)
    except sqlite3.Error as error:
        raise DatabaseSchemaError(
            "Omega could not create the action-history schema."
        ) from error


def _record_migration(
    connection: sqlite3.Connection,
    *,
    version: int,
    name: str,
) -> None:
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
            version,
            name,
            utc_timestamp(),
        ),
    )


def initialize_schema(
    connection: sqlite3.Connection,
) -> int:
    """Initialize all currently available schema versions."""

    try:
        connection.execute("BEGIN IMMEDIATE")

        apply_baseline_schema(connection)
        _record_migration(
            connection,
            version=BASELINE_SCHEMA_VERSION,
            name=BASELINE_MIGRATION_NAME,
        )

        apply_command_schema(connection)
        _record_migration(
            connection,
            version=COMMAND_SCHEMA_VERSION,
            name=COMMAND_MIGRATION_NAME,
        )

        apply_action_schema(connection)
        _record_migration(
            connection,
            version=ACTION_SCHEMA_VERSION,
            name=ACTION_MIGRATION_NAME,
        )

        connection.commit()

        return get_schema_version(connection)
    except Exception as error:
        if connection.in_transaction:
            connection.rollback()

        if isinstance(error, DatabaseSchemaError):
            raise

        raise DatabaseSchemaError(
            "Omega could not initialize the database schema."
        ) from error
