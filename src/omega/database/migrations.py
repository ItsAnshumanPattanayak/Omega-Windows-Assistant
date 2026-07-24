"""Transactional SQLite migration support."""

from __future__ import annotations

import sqlite3
from collections.abc import Callable, Iterable
from dataclasses import dataclass

from omega.core.exceptions import DatabaseMigrationError
from omega.database.connection import DatabaseConnectionFactory
from omega.database.schema import (
    ACTION_MIGRATION_NAME,
    ACTION_SCHEMA_VERSION,
    BASELINE_MIGRATION_NAME,
    BASELINE_SCHEMA_VERSION,
    COMMAND_MIGRATION_NAME,
    COMMAND_SCHEMA_VERSION,
    KNOWLEDGE_MIGRATION_NAME,
    KNOWLEDGE_SCHEMA_VERSION,
    PRODUCTIVITY_MIGRATION_NAME,
    PRODUCTIVITY_SCHEMA_VERSION,
    RECOVERY_MIGRATION_NAME,
    RECOVERY_SCHEMA_VERSION,
    SCHEDULING_MIGRATION_NAME,
    SCHEDULING_SCHEMA_VERSION,
    SETTINGS_MIGRATION_NAME,
    SETTINGS_SCHEMA_VERSION,
    apply_action_schema,
    apply_baseline_schema,
    apply_command_schema,
    apply_knowledge_schema,
    apply_productivity_schema,
    apply_recovery_schema,
    apply_scheduling_schema,
    apply_settings_schema,
    ensure_migrations_table,
    get_schema_version,
    utc_timestamp,
)

MigrationOperation = Callable[[sqlite3.Connection], None]


@dataclass(frozen=True)
class Migration:
    """One ordered database schema migration."""

    version: int
    name: str
    apply: MigrationOperation

    def __post_init__(self) -> None:
        if self.version <= 0:
            raise DatabaseMigrationError("Migration versions must be positive.")

        if not self.name.strip():
            raise DatabaseMigrationError("Migration names must not be empty.")


BASELINE_MIGRATION = Migration(
    version=BASELINE_SCHEMA_VERSION,
    name=BASELINE_MIGRATION_NAME,
    apply=apply_baseline_schema,
)

COMMAND_MIGRATION = Migration(
    version=COMMAND_SCHEMA_VERSION,
    name=COMMAND_MIGRATION_NAME,
    apply=apply_command_schema,
)

ACTION_MIGRATION = Migration(
    version=ACTION_SCHEMA_VERSION,
    name=ACTION_MIGRATION_NAME,
    apply=apply_action_schema,
)

RECOVERY_MIGRATION = Migration(
    version=RECOVERY_SCHEMA_VERSION,
    name=RECOVERY_MIGRATION_NAME,
    apply=apply_recovery_schema,
)

SETTINGS_MIGRATION = Migration(
    version=SETTINGS_SCHEMA_VERSION,
    name=SETTINGS_MIGRATION_NAME,
    apply=apply_settings_schema,
)
SCHEDULING_MIGRATION = Migration(
    SCHEDULING_SCHEMA_VERSION, SCHEDULING_MIGRATION_NAME, apply_scheduling_schema
)
PRODUCTIVITY_MIGRATION = Migration(
    PRODUCTIVITY_SCHEMA_VERSION,
    PRODUCTIVITY_MIGRATION_NAME,
    apply_productivity_schema,
)
KNOWLEDGE_MIGRATION = Migration(
    KNOWLEDGE_SCHEMA_VERSION,
    KNOWLEDGE_MIGRATION_NAME,
    apply_knowledge_schema,
)

DEFAULT_MIGRATIONS = (
    BASELINE_MIGRATION,
    COMMAND_MIGRATION,
    ACTION_MIGRATION,
    RECOVERY_MIGRATION,
    SETTINGS_MIGRATION,
    SCHEDULING_MIGRATION,
    PRODUCTIVITY_MIGRATION,
    KNOWLEDGE_MIGRATION,
)


class MigrationRunner:
    """Apply ordered SQLite schema migrations transactionally."""

    def __init__(
        self,
        connection_factory: DatabaseConnectionFactory,
        migrations: Iterable[Migration] = DEFAULT_MIGRATIONS,
    ) -> None:
        self.connection_factory = connection_factory
        self.migrations = tuple(
            sorted(
                migrations,
                key=lambda migration: migration.version,
            )
        )

        self._validate_migrations()

    def _validate_migrations(self) -> None:
        """Validate migration ordering, versions, and names."""

        versions = [migration.version for migration in self.migrations]

        if len(versions) != len(set(versions)):
            raise DatabaseMigrationError("Migration versions must be unique.")

        if versions:
            expected_versions = list(
                range(
                    1,
                    max(versions) + 1,
                )
            )

            if versions != expected_versions:
                raise DatabaseMigrationError(
                    "Migration versions must be contiguous " "and begin at version 1."
                )

        names = [migration.name for migration in self.migrations]

        if len(names) != len(set(names)):
            raise DatabaseMigrationError("Migration names must be unique.")

    def migrate(
        self,
        *,
        target_version: int | None = None,
    ) -> int:
        """Apply pending migrations and return the final version."""

        available_version = self.migrations[-1].version if self.migrations else 0

        selected_target = (
            available_version if target_version is None else target_version
        )

        if selected_target < 0 or selected_target > available_version:
            raise DatabaseMigrationError(
                "The requested migration target is not available."
            )

        connection = self.connection_factory.connect()

        try:
            ensure_migrations_table(connection)
            connection.commit()

            current_version = get_schema_version(connection)

            if current_version > selected_target:
                raise DatabaseMigrationError("Database downgrades are not supported.")

            pending_migrations = (
                migration
                for migration in self.migrations
                if (current_version < migration.version <= selected_target)
            )

            for migration in pending_migrations:
                self._apply_migration(
                    connection,
                    migration,
                )

            return get_schema_version(connection)
        finally:
            connection.close()

    def _apply_migration(
        self,
        connection: sqlite3.Connection,
        migration: Migration,
    ) -> None:
        """Apply one migration and its version record atomically."""

        try:
            connection.execute("BEGIN IMMEDIATE")

            migration.apply(connection)

            connection.execute(
                """
                INSERT INTO schema_migrations (
                    version,
                    name,
                    applied_at
                )
                VALUES (?, ?, ?)
                """,
                (
                    migration.version,
                    migration.name,
                    utc_timestamp(),
                ),
            )

            connection.commit()
        except Exception as error:
            if connection.in_transaction:
                connection.rollback()

            raise DatabaseMigrationError(
                "Database migration " f"{migration.version} failed."
            ) from error
