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
        assert [int(row["version"]) for row in rows] == [
            1,
            2,
            3,
            4,
            5,
            6,
            7,
            8,
        ]

        assert [str(row["name"]) for row in rows] == [
            "phase_9a_database_foundation",
            "phase_9b_command_repository",
            "phase_9c_action_repository",
            "phase_10_recovery_repository",
            "phase_10_runtime_settings",
            "phase_15_scheduling",
            "phase_16_productivity",
            "phase_17_knowledge",
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
            "recovery_records",
            "runtime_settings",
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


def test_phase10_indexes_and_recovery_foreign_keys(tmp_path: Path) -> None:
    connection = _factory(tmp_path).connect()
    try:
        initialize_schema(connection)
        indexes = {
            str(row[0])
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='index'"
            )
        }
        foreign_keys = {
            str(row["table"])
            for row in connection.execute("PRAGMA foreign_key_list(recovery_records)")
        }
        assert {
            "idx_recovery_status_expires",
            "idx_recovery_created_at",
            "idx_runtime_settings_updated_at",
        }.issubset(indexes)
        assert foreign_keys == {"commands", "actions"}
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

        assert first == 8
        assert second == 8
        assert count is not None
        assert int(count[0]) == 8
    finally:
        connection.close()


def test_scheduling_schema_has_due_claim_indexes_and_foreign_key(
    tmp_path: Path,
) -> None:
    connection = _factory(tmp_path).connect()
    try:
        initialize_schema(connection)
        indexes = {
            str(row[0])
            for row in connection.execute(
                "SELECT name FROM sqlite_master "
                "WHERE type='index' AND name LIKE 'idx_%schedule%' "
                "OR type='index' AND name LIKE 'idx_deliveries_%'"
            )
        }
        assert {
            "idx_schedules_status_due",
            "idx_schedules_type",
            "idx_deliveries_schedule",
            "idx_deliveries_claim_status",
        }.issubset(indexes)
        foreign_keys = connection.execute(
            "PRAGMA foreign_key_list(schedule_deliveries)"
        ).fetchall()
        assert {str(row["table"]) for row in foreign_keys} == {"scheduled_items"}
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
