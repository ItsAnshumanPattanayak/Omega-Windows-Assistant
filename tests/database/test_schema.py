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
        assert [int(row["version"]) for row in rows] == [1, 2]

        assert [str(row["name"]) for row in rows] == [
            "phase_9a_database_foundation",
            "phase_9b_command_repository",
        ]

        assert all(row["applied_at"] for row in rows)
    finally:
        connection.close()


def test_schema_initialization_creates_command_table_and_indexes(
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

        indexes = {
            str(row[0])
            for row in connection.execute(
                """
                SELECT name
                FROM sqlite_master
                WHERE type = 'index'
                AND name LIKE 'idx_commands_%'
                """
            )
        }

        assert "commands" in tables
        assert indexes == {
            "idx_commands_intent",
            "idx_commands_received_at",
            "idx_commands_session_id",
        }
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

        assert first == 2
        assert second == 2
        assert count is not None
        assert int(count[0]) == 2
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
