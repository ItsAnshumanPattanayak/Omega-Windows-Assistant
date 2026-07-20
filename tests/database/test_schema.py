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


def test_schema_initialization_creates_version_record(
    tmp_path: Path,
) -> None:
    connection = _factory(tmp_path).connect()

    try:
        version = initialize_schema(connection)

        row = connection.execute(
            """
            SELECT version, name, applied_at
            FROM schema_migrations
            """
        ).fetchone()

        assert version == LATEST_SCHEMA_VERSION
        assert row is not None
        assert int(row["version"]) == 1
        assert row["name"] == "phase_9a_database_foundation"
        assert row["applied_at"]
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

        assert first == 1
        assert second == 1
        assert count is not None
        assert int(count[0]) == 1
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
