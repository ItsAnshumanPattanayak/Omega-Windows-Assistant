"""Omega SQLite database foundation."""

from omega.database.configuration import (
    DatabaseConfiguration,
)
from omega.database.connection import (
    DatabaseConnectionFactory,
)
from omega.database.migrations import (
    BASELINE_MIGRATION,
    Migration,
    MigrationRunner,
)
from omega.database.schema import (
    BASELINE_MIGRATION_NAME,
    LATEST_SCHEMA_VERSION,
    apply_baseline_schema,
    ensure_migrations_table,
    get_schema_version,
    initialize_schema,
)

__all__ = [
    "BASELINE_MIGRATION",
    "BASELINE_MIGRATION_NAME",
    "LATEST_SCHEMA_VERSION",
    "DatabaseConfiguration",
    "DatabaseConnectionFactory",
    "Migration",
    "MigrationRunner",
    "apply_baseline_schema",
    "ensure_migrations_table",
    "get_schema_version",
    "initialize_schema",
]
