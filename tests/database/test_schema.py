from pathlib import Path

from omega.database import (
    LATEST_SCHEMA_VERSION,
    DatabaseConfiguration,
    DatabaseConnectionFactory,
    get_schema_version,
    initialize_schema,
)


def _factory(
    tmp_path: Path,
) -> DatabaseConnectionFactory:
    return DatabaseConnectionFactory(
        DatabaseConfiguration(),
        database_path=tmp_path / "omega.db",
    )


def test_schema_initialization_creates_all_version_records(
    tmp_path: Path,
) -> None:
    connection = _factory(tmp_path).connect()

    try:
        version = initialize_schema(connection)

        rows = connection.execute(
            """
            SELECT version, name, applied_at
            FROM schema_migrations
            ORDER BY version
            """
        ).fetchall()

        assert version == LATEST_SCHEMA_VERSION
        assert [int(row["version"]) for row in rows] == [1, 2, 3]

        assert [str(row["name"]) for row in rows] == [
            "phase_9a_database_foundation",
            "phase_9b_command_repository",
            "phase_9c_action_repository",
        ]

        assert all(row["applied_at"] for row in rows)
    finally:
        connection.close()


def test_schema_initialization_creates_history_tables(
    tmp_path: Path,
) -> None:
    connection = _factory(tmp_path).connect()

    try:
        initialize_schema(connection)

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

        assert {
            "schema_migrations",
            "commands",
            "actions",
            "action_results",
        }.issubset(tables)
    finally:
        connection.close()


def test_schema_initialization_creates_history_indexes(
    tmp_path: Path,
) -> None:
    connection = _factory(tmp_path).connect()

    try:
        initialize_schema(connection)

        indexes = {
            str(row[0])
            for row in connection.execute(
                """
                SELECT name
                FROM sqlite_master
                WHERE type = 'index'
                AND (
                    name LIKE 'idx_commands_%'
                    OR name LIKE 'idx_actions_%'
                )
                """
            )
        }

        assert indexes == {
            "idx_actions_command_id",
            "idx_actions_created_at",
            "idx_actions_intent",
            "idx_actions_status",
            "idx_commands_intent",
            "idx_commands_received_at",
            "idx_commands_session_id",
        }
    finally:
        connection.close()


def test_action_foreign_keys_are_enabled(
    tmp_path: Path,
) -> None:
    connection = _factory(tmp_path).connect()

    try:
        initialize_schema(connection)

        foreign_keys = connection.execute("PRAGMA foreign_keys").fetchone()

        assert foreign_keys is not None
        assert int(foreign_keys[0]) == 1
    finally:
        connection.close()


def test_schema_initialization_is_idempotent(
    tmp_path: Path,
) -> None:
    connection = _factory(tmp_path).connect()

    try:
        first = initialize_schema(connection)
        second = initialize_schema(connection)

        count = connection.execute(
            """
            SELECT COUNT(*)
            FROM schema_migrations
            """
        ).fetchone()

        assert first == 3
        assert second == 3
        assert count is not None
        assert int(count[0]) == 3
    finally:
        connection.close()


def test_new_database_starts_at_version_zero(
    tmp_path: Path,
) -> None:
    connection = _factory(tmp_path).connect()

    try:
        assert get_schema_version(connection) == 0
    finally:
        connection.close()
