import subprocess
import sys
from pathlib import Path

from omega.database import (
    DatabaseConfiguration,
    DatabaseConnectionFactory,
    MigrationRunner,
)
from omega.database.schema import KNOWLEDGE_SCHEMA_VERSION, LATEST_SCHEMA_VERSION
from omega.models import IntentType
from omega.understanding import CommandParser


def test_phase17_migration_is_contiguous() -> None:
    assert KNOWLEDGE_SCHEMA_VERSION == 8
    assert LATEST_SCHEMA_VERSION == 8


def test_knowledge_commands_use_existing_parser_and_preserve_queries() -> None:
    parser = CommandParser()
    cases = {
        "Create a knowledge collection called College Notes": (
            IntentType.CREATE_KNOWLEDGE_COLLECTION,
            "collection_name",
        ),
        "List documents in College Notes": (
            IntentType.LIST_KNOWLEDGE_DOCUMENTS,
            "collection_reference",
        ),
        "Search College Notes for database normalization": (
            IntentType.SEARCH_KNOWLEDGE,
            "knowledge_query",
        ),
        "Ask my documents what overfitting means": (
            IntentType.ASK_KNOWLEDGE,
            "knowledge_query",
        ),
        "Re-index the machine learning document": (
            IntentType.REINDEX_KNOWLEDGE_DOCUMENT,
            "document_reference",
        ),
        "Remove the old database document from my knowledge base": (
            IntentType.REMOVE_KNOWLEDGE_DOCUMENT,
            "document_reference",
        ),
        "Show the sources for that answer": (
            IntentType.SHOW_KNOWLEDGE_SOURCES,
            None,
        ),
        "Export these search results": (
            IntentType.EXPORT_KNOWLEDGE_RESULTS,
            None,
        ),
    }
    for text, (intent, entity_name) in cases.items():
        result = parser.parse(text)
        assert result.command.intent is intent
        assert not result.requires_clarification
        if entity_name is not None:
            assert any(item.name == entity_name for item in result.command.entities)


def test_importing_knowledge_has_no_database_model_worker_or_network_side_effect(
    tmp_path: Path,
) -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import pathlib,threading,socket;"
            "before=set(pathlib.Path('.').iterdir());"
            "socket.socket=lambda *a,**k: (_ for _ in ()).throw("
            "AssertionError('network attempted'));"
            "import omega.knowledge;"
            "assert before==set(pathlib.Path('.').iterdir());"
            "assert len(threading.enumerate())==1",
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )
    assert result.returncode == 0, result.stderr


def test_phase17_upgrade_preserves_phase16_and_adds_foreign_keys(
    tmp_path: Path,
) -> None:
    factory = DatabaseConnectionFactory(
        DatabaseConfiguration(), database_path=tmp_path / "omega.db"
    )
    runner = MigrationRunner(factory)
    assert runner.migrate(target_version=7) == 7
    connection = factory.connect()
    try:
        connection.execute(
            "INSERT INTO task_lists (task_list_id,name,description,is_archived,"
            "created_at,updated_at,archived_at,metadata_json,revision) "
            "VALUES ('list','Existing','','0','2026-01-01T00:00:00+00:00',"
            "'2026-01-01T00:00:00+00:00',NULL,'{}',1)"
        )
        connection.commit()
    finally:
        connection.close()
    assert runner.migrate() == 8
    connection = factory.connect()
    try:
        assert (
            connection.execute(
                "SELECT name FROM task_lists WHERE task_list_id='list'"
            ).fetchone()["name"]
            == "Existing"
        )
        tables = {
            row["name"]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
        assert {
            "knowledge_collections",
            "knowledge_documents",
            "knowledge_chunks",
            "knowledge_semantic_entries",
        }.issubset(tables)
        foreign_keys = connection.execute(
            "PRAGMA foreign_key_list(knowledge_chunks)"
        ).fetchall()
        assert {row["table"] for row in foreign_keys} == {"knowledge_documents"}
        assert connection.execute("PRAGMA foreign_keys").fetchone()[0] == 1
    finally:
        connection.close()
