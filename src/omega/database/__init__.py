"""Omega SQLite database and repository foundation."""

from omega.database.command_repository import CommandRepository
from omega.database.configuration import DatabaseConfiguration
from omega.database.connection import DatabaseConnectionFactory
from omega.database.migrations import (
    BASELINE_MIGRATION,
    COMMAND_MIGRATION,
    DEFAULT_MIGRATIONS,
    Migration,
    MigrationRunner,
)
from omega.database.schema import (
    BASELINE_MIGRATION_NAME,
    BASELINE_SCHEMA_VERSION,
    COMMAND_MIGRATION_NAME,
    COMMAND_SCHEMA_VERSION,
    LATEST_SCHEMA_VERSION,
    apply_baseline_schema,
    apply_command_schema,
    ensure_migrations_table,
    get_schema_version,
    initialize_schema,
)

__all__ = [
    "BASELINE_MIGRATION",
    "BASELINE_MIGRATION_NAME",
    "BASELINE_SCHEMA_VERSION",
    "COMMAND_MIGRATION",
    "COMMAND_MIGRATION_NAME",
    "COMMAND_SCHEMA_VERSION",
    "DEFAULT_MIGRATIONS",
    "LATEST_SCHEMA_VERSION",
    "CommandRepository",
    "DatabaseConfiguration",
    "DatabaseConnectionFactory",
    "Migration",
    "MigrationRunner",
    "apply_baseline_schema",
    "apply_command_schema",
    "ensure_migrations_table",
    "get_schema_version",
    "initialize_schema",
]
