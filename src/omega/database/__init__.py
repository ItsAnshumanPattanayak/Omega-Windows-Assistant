"""Omega SQLite database and repository foundation."""

from omega.database.action_repository import ActionRepository
from omega.database.command_repository import CommandRepository
from omega.database.configuration import DatabaseConfiguration
from omega.database.connection import DatabaseConnectionFactory
from omega.database.migrations import (
    ACTION_MIGRATION,
    BASELINE_MIGRATION,
    COMMAND_MIGRATION,
    DEFAULT_MIGRATIONS,
    Migration,
    MigrationRunner,
)
from omega.database.schema import (
    ACTION_MIGRATION_NAME,
    ACTION_SCHEMA_VERSION,
    BASELINE_MIGRATION_NAME,
    BASELINE_SCHEMA_VERSION,
    COMMAND_MIGRATION_NAME,
    COMMAND_SCHEMA_VERSION,
    LATEST_SCHEMA_VERSION,
    apply_action_schema,
    apply_baseline_schema,
    apply_command_schema,
    ensure_migrations_table,
    get_schema_version,
    initialize_schema,
)

__all__ = [
    "ACTION_MIGRATION",
    "ACTION_MIGRATION_NAME",
    "ACTION_SCHEMA_VERSION",
    "BASELINE_MIGRATION",
    "BASELINE_MIGRATION_NAME",
    "BASELINE_SCHEMA_VERSION",
    "COMMAND_MIGRATION",
    "COMMAND_MIGRATION_NAME",
    "COMMAND_SCHEMA_VERSION",
    "DEFAULT_MIGRATIONS",
    "LATEST_SCHEMA_VERSION",
    "ActionRepository",
    "CommandRepository",
    "DatabaseConfiguration",
    "DatabaseConnectionFactory",
    "Migration",
    "MigrationRunner",
    "apply_action_schema",
    "apply_baseline_schema",
    "apply_command_schema",
    "ensure_migrations_table",
    "get_schema_version",
    "initialize_schema",
]
