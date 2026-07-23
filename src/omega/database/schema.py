"""Omega SQLite schema definitions and initialization."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime

from omega.core.exceptions import DatabaseSchemaError

BASELINE_SCHEMA_VERSION = 1
COMMAND_SCHEMA_VERSION = 2
ACTION_SCHEMA_VERSION = 3
RECOVERY_SCHEMA_VERSION = 4
SETTINGS_SCHEMA_VERSION = 5
SCHEDULING_SCHEMA_VERSION = 6
PRODUCTIVITY_SCHEMA_VERSION = 7
LATEST_SCHEMA_VERSION = PRODUCTIVITY_SCHEMA_VERSION

BASELINE_MIGRATION_NAME = "phase_9a_database_foundation"
COMMAND_MIGRATION_NAME = "phase_9b_command_repository"
ACTION_MIGRATION_NAME = "phase_9c_action_repository"
RECOVERY_MIGRATION_NAME = "phase_10_recovery_repository"
SETTINGS_MIGRATION_NAME = "phase_10_runtime_settings"
SCHEDULING_MIGRATION_NAME = "phase_15_scheduling"
PRODUCTIVITY_MIGRATION_NAME = "phase_16_productivity"

CREATE_SCHEDULED_ITEMS_TABLE = """
CREATE TABLE IF NOT EXISTS scheduled_items (
 schedule_id TEXT PRIMARY KEY, schedule_type TEXT NOT NULL, title TEXT NOT NULL,
 message TEXT NOT NULL, status TEXT NOT NULL, due_at_utc TEXT NOT NULL,
 timezone_name TEXT NOT NULL, recurrence_json TEXT, created_at TEXT NOT NULL,
 updated_at TEXT NOT NULL, completed_at TEXT, cancelled_at TEXT,
 snoozed_until_utc TEXT, remaining_seconds INTEGER, occurrence_count INTEGER NOT NULL,
 revision INTEGER NOT NULL, metadata_json TEXT NOT NULL,
 CHECK(schedule_type IN ('reminder','alarm','timer')),
 CHECK(status IN ('pending','paused','snoozed','completed','cancelled','missed')),
 CHECK(revision >= 1), CHECK(occurrence_count >= 0),
 CHECK(remaining_seconds IS NULL OR remaining_seconds > 0)
)
"""
CREATE_SCHEDULE_DELIVERIES_TABLE = """
CREATE TABLE IF NOT EXISTS schedule_deliveries (
 delivery_id TEXT PRIMARY KEY, schedule_id TEXT NOT NULL,
 occurrence_at_utc TEXT NOT NULL, claimed_at TEXT NOT NULL,
 delivered_at TEXT, delivery_status TEXT NOT NULL, attempt_count INTEGER NOT NULL,
 error_code TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
 FOREIGN KEY(schedule_id) REFERENCES scheduled_items(schedule_id) ON DELETE CASCADE,
 UNIQUE(schedule_id, occurrence_at_utc),
 CHECK(delivery_status IN ('claimed','delivered','failed','missed')),
 CHECK(attempt_count >= 1)
)
"""

CREATE_NOTES_TABLE = """
CREATE TABLE IF NOT EXISTS notes (
 note_id TEXT PRIMARY KEY, title TEXT NOT NULL, body TEXT NOT NULL,
 is_pinned INTEGER NOT NULL, is_archived INTEGER NOT NULL,
 created_at TEXT NOT NULL, updated_at TEXT NOT NULL, archived_at TEXT,
 source_command_id TEXT, metadata_json TEXT NOT NULL, revision INTEGER NOT NULL,
 FOREIGN KEY(source_command_id) REFERENCES commands(command_id) ON DELETE SET NULL,
 CHECK(is_pinned IN (0,1)), CHECK(is_archived IN (0,1)), CHECK(revision >= 1),
 CHECK(length(trim(title)) > 0 OR length(trim(body)) > 0),
 CHECK((is_archived=1 AND archived_at IS NOT NULL) OR
       (is_archived=0 AND archived_at IS NULL))
)
"""
CREATE_TASK_LISTS_TABLE = """
CREATE TABLE IF NOT EXISTS task_lists (
 task_list_id TEXT PRIMARY KEY, name TEXT NOT NULL COLLATE NOCASE,
 description TEXT NOT NULL, is_archived INTEGER NOT NULL,
 created_at TEXT NOT NULL, updated_at TEXT NOT NULL, archived_at TEXT,
 metadata_json TEXT NOT NULL, revision INTEGER NOT NULL,
 UNIQUE(name), CHECK(length(trim(name)) > 0), CHECK(is_archived IN (0,1)),
 CHECK(revision >= 1), CHECK((is_archived=1 AND archived_at IS NOT NULL) OR
 (is_archived=0 AND archived_at IS NULL))
)
"""
CREATE_TASKS_TABLE = """
CREATE TABLE IF NOT EXISTS tasks (
 task_id TEXT PRIMARY KEY, task_list_id TEXT NOT NULL, title TEXT NOT NULL,
 description TEXT NOT NULL, status TEXT NOT NULL, priority TEXT NOT NULL,
 due_at_utc TEXT, completed_at TEXT, cancelled_at TEXT,
 is_archived INTEGER NOT NULL, archived_at TEXT, created_at TEXT NOT NULL,
 updated_at TEXT NOT NULL, source_command_id TEXT, metadata_json TEXT NOT NULL,
 revision INTEGER NOT NULL,
 FOREIGN KEY(task_list_id) REFERENCES task_lists(task_list_id) ON DELETE CASCADE,
 FOREIGN KEY(source_command_id) REFERENCES commands(command_id) ON DELETE SET NULL,
 CHECK(status IN ('pending','in_progress','completed','cancelled')),
 CHECK(priority IN ('none','low','medium','high','urgent')),
 CHECK(is_archived IN (0,1)), CHECK(revision >= 1),
 CHECK(length(trim(title)) > 0),
 CHECK((status='completed' AND completed_at IS NOT NULL AND cancelled_at IS NULL) OR
       (status='cancelled' AND cancelled_at IS NOT NULL AND completed_at IS NULL) OR
       (status IN ('pending','in_progress') AND completed_at IS NULL
        AND cancelled_at IS NULL)),
 CHECK((is_archived=1 AND archived_at IS NOT NULL) OR
       (is_archived=0 AND archived_at IS NULL))
)
"""
CREATE_TAGS_TABLE = """
CREATE TABLE IF NOT EXISTS tags (
 tag_id TEXT PRIMARY KEY, normalized_name TEXT NOT NULL UNIQUE,
 display_name TEXT NOT NULL, created_at TEXT NOT NULL,
 CHECK(length(trim(normalized_name)) > 0)
)
"""
CREATE_NOTE_TAGS_TABLE = """
CREATE TABLE IF NOT EXISTS note_tags (
 note_id TEXT NOT NULL, tag_id TEXT NOT NULL, PRIMARY KEY(note_id,tag_id),
 FOREIGN KEY(note_id) REFERENCES notes(note_id) ON DELETE CASCADE,
 FOREIGN KEY(tag_id) REFERENCES tags(tag_id) ON DELETE CASCADE
)
"""
CREATE_TASK_TAGS_TABLE = """
CREATE TABLE IF NOT EXISTS task_tags (
 task_id TEXT NOT NULL, tag_id TEXT NOT NULL, PRIMARY KEY(task_id,tag_id),
 FOREIGN KEY(task_id) REFERENCES tasks(task_id) ON DELETE CASCADE,
 FOREIGN KEY(tag_id) REFERENCES tags(tag_id) ON DELETE CASCADE
)
"""
CREATE_TASK_REMINDER_LINKS_TABLE = """
CREATE TABLE IF NOT EXISTS task_reminder_links (
 task_id TEXT NOT NULL, schedule_id TEXT NOT NULL, link_type TEXT NOT NULL,
 created_at TEXT NOT NULL, PRIMARY KEY(task_id,schedule_id),
 FOREIGN KEY(task_id) REFERENCES tasks(task_id) ON DELETE CASCADE,
 FOREIGN KEY(schedule_id) REFERENCES scheduled_items(schedule_id) ON DELETE RESTRICT,
 CHECK(link_type IN ('deadline','manual'))
)
"""

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

CREATE_RECOVERY_RECORDS_TABLE = """
CREATE TABLE IF NOT EXISTS recovery_records (
    record_id TEXT PRIMARY KEY,
    action_type TEXT NOT NULL,
    resource_type TEXT NOT NULL,
    command_id TEXT NOT NULL,
    action_id TEXT NOT NULL,
    session_id TEXT NOT NULL,
    display_name TEXT NOT NULL,
    logical_location TEXT NOT NULL,
    relative_path TEXT NOT NULL,
    original_path_fingerprint TEXT NOT NULL,
    recycle_bin_reference TEXT,
    size_bytes INTEGER,
    recycled_at TEXT NOT NULL,
    item_metadata_json TEXT NOT NULL,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    expires_at TEXT,
    restored_at TEXT,
    failure_code TEXT,
    metadata_json TEXT NOT NULL,
    FOREIGN KEY (command_id) REFERENCES commands(command_id) ON DELETE CASCADE,
    FOREIGN KEY (action_id) REFERENCES actions(action_id) ON DELETE CASCADE,
    CHECK (size_bytes IS NULL OR size_bytes >= 0)
)
"""

CREATE_RECOVERY_STATUS_INDEX = """
CREATE INDEX IF NOT EXISTS idx_recovery_status_expires
ON recovery_records(status, expires_at)
"""

CREATE_RECOVERY_CREATED_INDEX = """
CREATE INDEX IF NOT EXISTS idx_recovery_created_at
ON recovery_records(created_at DESC, record_id DESC)
"""

CREATE_RUNTIME_SETTINGS_TABLE = """
CREATE TABLE IF NOT EXISTS runtime_settings (
    name TEXT PRIMARY KEY,
    value_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
)
"""

CREATE_RUNTIME_SETTINGS_UPDATED_INDEX = """
CREATE INDEX IF NOT EXISTS idx_runtime_settings_updated_at
ON runtime_settings(updated_at DESC)
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


def apply_recovery_schema(connection: sqlite3.Connection) -> None:
    """Create persistent recovery-record storage."""

    try:
        connection.execute(CREATE_RECOVERY_RECORDS_TABLE)
        connection.execute(CREATE_RECOVERY_STATUS_INDEX)
        connection.execute(CREATE_RECOVERY_CREATED_INDEX)
    except sqlite3.Error as error:
        raise DatabaseSchemaError(
            "Omega could not create the recovery-history schema."
        ) from error


def apply_settings_schema(connection: sqlite3.Connection) -> None:
    """Create mutable runtime-settings storage."""

    try:
        connection.execute(CREATE_RUNTIME_SETTINGS_TABLE)
        connection.execute(CREATE_RUNTIME_SETTINGS_UPDATED_INDEX)
    except sqlite3.Error as error:
        raise DatabaseSchemaError(
            "Omega could not create the runtime-settings schema."
        ) from error


def apply_scheduling_schema(connection: sqlite3.Connection) -> None:
    """Create persistent schedules and atomic delivery claims."""
    try:
        connection.execute(CREATE_SCHEDULED_ITEMS_TABLE)
        connection.execute(CREATE_SCHEDULE_DELIVERIES_TABLE)
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_schedules_status_due "
            "ON scheduled_items(status,due_at_utc)"
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_schedules_type "
            "ON scheduled_items(schedule_type)"
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_deliveries_schedule "
            "ON schedule_deliveries(schedule_id,occurrence_at_utc)"
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_deliveries_claim_status "
            "ON schedule_deliveries(delivery_status,claimed_at)"
        )
    except sqlite3.Error as error:
        raise DatabaseSchemaError(
            "Omega could not create the scheduling schema."
        ) from error


def apply_productivity_schema(connection: sqlite3.Connection) -> None:
    """Create revisioned notes, tasks, tags, and schedule links."""

    try:
        for statement in (
            CREATE_NOTES_TABLE,
            CREATE_TASK_LISTS_TABLE,
            CREATE_TASKS_TABLE,
            CREATE_TAGS_TABLE,
            CREATE_NOTE_TAGS_TABLE,
            CREATE_TASK_TAGS_TABLE,
            CREATE_TASK_REMINDER_LINKS_TABLE,
            "CREATE INDEX IF NOT EXISTS idx_notes_archive_update "
            "ON notes(is_archived,updated_at DESC)",
            "CREATE INDEX IF NOT EXISTS idx_notes_pinned "
            "ON notes(is_pinned,updated_at DESC)",
            "CREATE INDEX IF NOT EXISTS idx_lists_archive_name "
            "ON task_lists(is_archived,name)",
            "CREATE INDEX IF NOT EXISTS idx_tasks_list_status "
            "ON tasks(task_list_id,status)",
            "CREATE INDEX IF NOT EXISTS idx_tasks_due ON tasks(due_at_utc)",
            "CREATE INDEX IF NOT EXISTS idx_tasks_priority ON tasks(priority)",
            "CREATE INDEX IF NOT EXISTS idx_tasks_archive_update "
            "ON tasks(is_archived,updated_at DESC)",
            "CREATE INDEX IF NOT EXISTS idx_tags_normalized ON tags(normalized_name)",
            "CREATE INDEX IF NOT EXISTS idx_links_schedule "
            "ON task_reminder_links(schedule_id)",
        ):
            connection.execute(statement)
    except sqlite3.Error as error:
        raise DatabaseSchemaError(
            "Omega could not create the productivity schema."
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

        apply_recovery_schema(connection)
        _record_migration(
            connection,
            version=RECOVERY_SCHEMA_VERSION,
            name=RECOVERY_MIGRATION_NAME,
        )

        apply_settings_schema(connection)
        _record_migration(
            connection,
            version=SETTINGS_SCHEMA_VERSION,
            name=SETTINGS_MIGRATION_NAME,
        )
        apply_scheduling_schema(connection)
        _record_migration(
            connection,
            version=SCHEDULING_SCHEMA_VERSION,
            name=SCHEDULING_MIGRATION_NAME,
        )
        apply_productivity_schema(connection)
        _record_migration(
            connection,
            version=PRODUCTIVITY_SCHEMA_VERSION,
            name=PRODUCTIVITY_MIGRATION_NAME,
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
