"""Omega SQLite database and repository foundation."""

from omega.database.action_repository import ActionRepository
from omega.database.command_repository import CommandRepository
from omega.database.configuration import DatabaseConfiguration
from omega.database.connection import DatabaseConnectionFactory
from omega.database.lifecycle import ExecutionPersistence
from omega.database.migrations import (
    ACTION_MIGRATION,
    BASELINE_MIGRATION,
    COMMAND_MIGRATION,
    DEFAULT_MIGRATIONS,
    RECOVERY_MIGRATION,
    SETTINGS_MIGRATION,
    Migration,
    MigrationRunner,
)
from omega.database.recovery_repository import SqliteRecoveryRecordStore
from omega.database.schema import (
    ACTION_MIGRATION_NAME,
    ACTION_SCHEMA_VERSION,
    BASELINE_MIGRATION_NAME,
    BASELINE_SCHEMA_VERSION,
    COMMAND_MIGRATION_NAME,
    COMMAND_SCHEMA_VERSION,
    LATEST_SCHEMA_VERSION,
    RECOVERY_MIGRATION_NAME,
    RECOVERY_SCHEMA_VERSION,
    SETTINGS_MIGRATION_NAME,
    SETTINGS_SCHEMA_VERSION,
    apply_action_schema,
    apply_baseline_schema,
    apply_command_schema,
    apply_recovery_schema,
    apply_settings_schema,
    ensure_migrations_table,
    get_schema_version,
    initialize_schema,
)
from omega.database.settings_repository import RuntimeSetting, RuntimeSettingsRepository

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
    "RECOVERY_MIGRATION",
    "RECOVERY_MIGRATION_NAME",
    "RECOVERY_SCHEMA_VERSION",
    "SETTINGS_MIGRATION",
    "SETTINGS_MIGRATION_NAME",
    "SETTINGS_SCHEMA_VERSION",
    "ActionRepository",
    "CommandRepository",
    "DatabaseConfiguration",
    "DatabaseConnectionFactory",
    "ExecutionPersistence",
    "Migration",
    "MigrationRunner",
    "RuntimeSetting",
    "RuntimeSettingsRepository",
    "SqliteRecoveryRecordStore",
    "apply_action_schema",
    "apply_baseline_schema",
    "apply_command_schema",
    "apply_recovery_schema",
    "apply_settings_schema",
    "ensure_migrations_table",
    "get_schema_version",
    "initialize_schema",
]
