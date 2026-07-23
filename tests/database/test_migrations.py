import sqlite3
from pathlib import Path

import pytest

from omega.core.exceptions import DatabaseMigrationError
from omega.database import (
    DatabaseConfiguration,
    DatabaseConnectionFactory,
    Migration,
    MigrationRunner,
)


def _factory(
    tmp_path: Path,
) -> DatabaseConnectionFactory:
    return DatabaseConnectionFactory(
        DatabaseConfiguration(),
        database_path=tmp_path / "omega.db",
    )


def test_default_migrations_apply_once(
    tmp_path: Path,
) -> None:
    factory = _factory(tmp_path)
    runner = MigrationRunner(factory)

    first = runner.migrate()
    second = runner.migrate()

    assert first == 7
    assert second == 7

    connection = factory.connect()

    try:
        versions = [
            int(row[0])
            for row in connection.execute(
                """
                SELECT version
                FROM schema_migrations
                ORDER BY version
                """
            )
        ]

        assert versions == [1, 2, 3, 4, 5, 6, 7]
    finally:
        connection.close()


@pytest.mark.parametrize(
    ("target_version", "expected_tables"),
    [
        (
            1,
            {
                "schema_migrations",
            },
        ),
        (
            2,
            {
                "schema_migrations",
                "commands",
            },
        ),
        (
            3,
            {
                "schema_migrations",
                "commands",
                "actions",
                "action_results",
            },
        ),
        (
            4,
            {
                "schema_migrations",
                "commands",
                "actions",
                "action_results",
                "recovery_records",
            },
        ),
        (
            5,
            {
                "schema_migrations",
                "commands",
                "actions",
                "action_results",
                "recovery_records",
                "runtime_settings",
            },
        ),
        (
            6,
            {
                "schema_migrations",
                "commands",
                "actions",
                "action_results",
                "recovery_records",
                "runtime_settings",
                "scheduled_items",
                "schedule_deliveries",
            },
        ),
    ],
)
def test_runner_can_stop_at_requested_target(
    tmp_path: Path,
    target_version: int,
    expected_tables: set[str],
) -> None:
    factory = _factory(tmp_path)
    runner = MigrationRunner(factory)

    assert runner.migrate(target_version=target_version) == target_version

    connection = factory.connect()

    try:
        tables = {
            str(row[0])
            for row in connection.execute(
                """
                SELECT name
                FROM sqlite_master
                WHERE type = 'table'
                """
            )
            if not str(row[0]).startswith("sqlite_")
        }

        assert tables == expected_tables
    finally:
        connection.close()


@pytest.mark.parametrize("starting_version", [1, 2, 3, 5])
def test_phase10_upgrade_preserves_existing_schema(
    tmp_path: Path, starting_version: int
) -> None:
    factory = _factory(tmp_path)
    runner = MigrationRunner(factory)
    runner.migrate(target_version=starting_version)

    assert runner.migrate() == 7

    connection = factory.connect()
    try:
        versions = [
            int(row[0])
            for row in connection.execute(
                "SELECT version FROM schema_migrations ORDER BY version"
            )
        ]
        tables = {
            str(row[0])
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
        assert versions == [1, 2, 3, 4, 5, 6, 7]
        assert {"recovery_records", "runtime_settings"}.issubset(tables)
    finally:
        connection.close()


def test_migration_runner_applies_custom_ordered_migrations(
    tmp_path: Path,
) -> None:
    factory = _factory(tmp_path)

    def migration_one(
        connection: sqlite3.Connection,
    ) -> None:
        connection.execute(
            """
            CREATE TABLE first_table (
                id INTEGER PRIMARY KEY
            )
            """
        )

    def migration_two(
        connection: sqlite3.Connection,
    ) -> None:
        connection.execute(
            """
            CREATE TABLE second_table (
                id INTEGER PRIMARY KEY
            )
            """
        )

    runner = MigrationRunner(
        factory,
        migrations=(
            Migration(
                1,
                "create_first_table",
                migration_one,
            ),
            Migration(
                2,
                "create_second_table",
                migration_two,
            ),
        ),
    )

    assert runner.migrate() == 2

    connection = factory.connect()

    try:
        tables = {
            str(row[0])
            for row in connection.execute(
                """
                SELECT name
                FROM sqlite_master
                WHERE type = 'table'
                """
            )
        }

        assert "first_table" in tables
        assert "second_table" in tables
    finally:
        connection.close()


def test_failed_migration_rolls_back(
    tmp_path: Path,
) -> None:
    factory = _factory(tmp_path)

    def migration_one(
        connection: sqlite3.Connection,
    ) -> None:
        connection.execute(
            """
            CREATE TABLE stable_table (
                id INTEGER PRIMARY KEY
            )
            """
        )

    def migration_two(
        connection: sqlite3.Connection,
    ) -> None:
        connection.execute(
            """
            CREATE TABLE rolled_back_table (
                id INTEGER PRIMARY KEY
            )
            """
        )
        raise RuntimeError("forced migration failure")

    runner = MigrationRunner(
        factory,
        migrations=(
            Migration(
                1,
                "create_stable_table",
                migration_one,
            ),
            Migration(
                2,
                "force_failure",
                migration_two,
            ),
        ),
    )

    with pytest.raises(
        DatabaseMigrationError,
        match="migration 2 failed",
    ):
        runner.migrate()

    connection = factory.connect()

    try:
        tables = {
            str(row[0])
            for row in connection.execute(
                """
                SELECT name
                FROM sqlite_master
                WHERE type = 'table'
                """
            )
        }

        versions = [
            int(row[0])
            for row in connection.execute(
                """
                SELECT version
                FROM schema_migrations
                ORDER BY version
                """
            )
        ]

        assert "stable_table" in tables
        assert "rolled_back_table" not in tables
        assert versions == [1]
    finally:
        connection.close()


@pytest.mark.parametrize(
    "migrations",
    [
        (
            Migration(
                1,
                "first",
                lambda connection: None,
            ),
            Migration(
                1,
                "duplicate_version",
                lambda connection: None,
            ),
        ),
        (
            Migration(
                1,
                "duplicate_name",
                lambda connection: None,
            ),
            Migration(
                2,
                "duplicate_name",
                lambda connection: None,
            ),
        ),
        (
            Migration(
                2,
                "missing_first",
                lambda connection: None,
            ),
        ),
    ],
)
def test_invalid_migration_sequences_are_rejected(
    tmp_path: Path,
    migrations: tuple[Migration, ...],
) -> None:
    with pytest.raises(DatabaseMigrationError):
        MigrationRunner(
            _factory(tmp_path),
            migrations=migrations,
        )
