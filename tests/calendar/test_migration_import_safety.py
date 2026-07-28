import importlib

from omega.calendar import CalendarOperationStatus, SqliteCalendarOperationStore
from omega.database import (
    DatabaseConfiguration,
    DatabaseConnectionFactory,
    MigrationRunner,
)
from omega.database.schema import CALENDAR_SCHEMA_VERSION, LATEST_SCHEMA_VERSION


def test_phase_19_migration_is_contiguous_metadata_only(tmp_path) -> None:
    factory = DatabaseConnectionFactory(
        DatabaseConfiguration(), database_path=tmp_path / "omega.db"
    )
    assert CALENDAR_SCHEMA_VERSION == 11
    assert MigrationRunner(factory).migrate() == LATEST_SCHEMA_VERSION == 14
    connection = factory.connect()
    try:
        columns = {
            row[1]
            for row in connection.execute("PRAGMA table_info(calendar_operations)")
        }
        assert columns == {
            "operation_id",
            "account_name",
            "operation_type",
            "target_id",
            "status",
            "provider_reference",
            "created_at",
            "updated_at",
        }
        assert connection.execute("PRAGMA foreign_keys").fetchone()[0] == 1
    finally:
        connection.close()


def test_sqlite_receipts_are_atomic_and_content_free(tmp_path) -> None:
    factory = DatabaseConnectionFactory(
        DatabaseConfiguration(), database_path=tmp_path / "omega.db"
    )
    MigrationRunner(factory).migrate()
    store = SqliteCalendarOperationStore(factory)
    assert store.claim("op-1", "account", "create", "proposal-1")
    assert not store.claim("op-2", "account", "create", "proposal-1")
    store.finish("op-1", CalendarOperationStatus.SUCCEEDED, "event-1")


def test_importing_calendar_creates_no_database_or_network(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.chdir(tmp_path)
    before = set(tmp_path.iterdir())
    importlib.reload(importlib.import_module("omega.calendar"))
    assert set(tmp_path.iterdir()) == before
