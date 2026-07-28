from __future__ import annotations

import importlib
import sqlite3

from omega.database import (
    DatabaseConfiguration,
    DatabaseConnectionFactory,
    MigrationRunner,
)
from omega.database.schema import EMAIL_SCHEMA_VERSION, LATEST_SCHEMA_VERSION
from omega.email import SqliteEmailOperationStore
from omega.email.models import EmailOperationStatus


def test_phase_18_migration_is_contiguous_and_metadata_only(tmp_path) -> None:
    factory = DatabaseConnectionFactory(
        DatabaseConfiguration(), database_path=tmp_path / "omega.db"
    )
    assert EMAIL_SCHEMA_VERSION == 10
    assert MigrationRunner(factory).migrate() == LATEST_SCHEMA_VERSION == 14
    connection = factory.connect()
    try:
        columns = {
            str(row[1])
            for row in connection.execute("PRAGMA table_info(email_operations)")
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
        assert not columns.intersection({"body", "password", "token", "attachment"})
        foreign_keys = connection.execute("PRAGMA foreign_keys").fetchone()
        assert foreign_keys is not None and int(foreign_keys[0]) == 1
    finally:
        connection.close()


def test_existing_phase_17_database_migrates_without_data_loss(tmp_path) -> None:
    factory = DatabaseConnectionFactory(
        DatabaseConfiguration(), database_path=tmp_path / "omega.db"
    )
    runner = MigrationRunner(factory)
    assert runner.migrate(target_version=9) == 9
    connection = factory.connect()
    try:
        connection.execute(
            "INSERT INTO knowledge_collections("
            "collection_id,name,description,is_archived,created_at,updated_at,"
            "archived_at,metadata_json,revision) VALUES(?,?,?,?,?,?,?,?,?)",
            (
                "collection-1",
                "Existing",
                "",
                0,
                "2026-01-01T00:00:00+00:00",
                "2026-01-01T00:00:00+00:00",
                None,
                "{}",
                1,
            ),
        )
        connection.commit()
    finally:
        connection.close()
    assert runner.migrate() == 14
    connection = factory.connect()
    try:
        assert (
            connection.execute("SELECT name FROM knowledge_collections").fetchone()[0]
            == "Existing"
        )
    finally:
        connection.close()


def test_sqlite_receipts_atomically_block_duplicate_target(tmp_path) -> None:
    factory = DatabaseConnectionFactory(
        DatabaseConfiguration(), database_path=tmp_path / "omega.db"
    )
    MigrationRunner(factory).migrate()
    store = SqliteEmailOperationStore(factory)
    assert store.claim("operation-1", "account", "send", "draft-1")
    assert not store.claim("operation-2", "account", "send", "draft-1")
    store.finish("operation-1", EmailOperationStatus.AMBIGUOUS)
    assert not store.claim("operation-3", "account", "send", "draft-1")


def test_importing_email_modules_creates_no_schema_or_network(monkeypatch) -> None:
    called = []

    def fail_connect(*args, **kwargs):
        called.append((args, kwargs))
        raise AssertionError("network access attempted during import")

    monkeypatch.setattr("socket.create_connection", fail_connect)
    importlib.reload(importlib.import_module("omega.email"))
    assert called == []


def test_schema_has_no_credentials_or_body_columns() -> None:
    connection = sqlite3.connect(":memory:")
    from omega.database.schema import apply_email_schema

    apply_email_schema(connection)
    sql = (
        connection.execute(
            "SELECT sql FROM sqlite_master WHERE name='email_operations'"
        )
        .fetchone()[0]
        .casefold()
    )
    assert "password" not in sql
    assert "token" not in sql
    assert "body" not in sql
