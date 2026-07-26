from pathlib import Path

import pytest

from omega.knowledge import (
    KnowledgeConfiguration,
    KnowledgeSearchQuery,
    KnowledgeSourceStatus,
)
from omega.knowledge.exceptions import DocumentImportError, DocumentValidationError
from omega.models import IntentType
from omega.understanding import CommandParser


def test_directory_import_is_non_recursive_bounded_and_deterministic(
    tmp_path: Path, knowledge: tuple[object, object, object]
) -> None:
    service, repository, _configuration = knowledge
    collection = service.create_collection("Folder")  # type: ignore[attr-defined]
    (tmp_path / "b.txt").write_text("Second local source.", encoding="utf-8")
    (tmp_path / "a.md").write_text("# First\nKnown phrase.", encoding="utf-8")
    (tmp_path / "ignored.exe").write_bytes(b"MZ")
    nested = tmp_path / "nested"
    nested.mkdir()
    (nested / "nested.txt").write_text("Not indexed by default.", encoding="utf-8")

    result = service.import_directory(tmp_path, collection)  # type: ignore[attr-defined]

    assert result.documents_indexed == 2
    assert result.skipped >= 1
    assert sorted(
        item.original_filename for item in repository.list_documents()  # type: ignore[attr-defined]
    ) == [
        "a.md",
        "b.txt",
    ]
    recursive = service.import_directory(  # type: ignore[attr-defined]
        tmp_path, collection, recursive=True
    )
    assert recursive.documents_indexed == 1
    assert recursive.duplicates == 2


def test_directory_limits_fail_before_import(
    tmp_path: Path, knowledge: tuple[object, object, object]
) -> None:
    service, _repository, _configuration = knowledge
    service.validator.configuration = KnowledgeConfiguration(  # type: ignore[attr-defined,misc]
        maximum_files_per_request=1
    )
    (tmp_path / "one.txt").write_text("one", encoding="utf-8")
    (tmp_path / "two.txt").write_text("two", encoding="utf-8")
    with pytest.raises(DocumentValidationError):
        service.validator.discover_directory(tmp_path)  # type: ignore[attr-defined]


def test_source_status_change_missing_and_duplicate_path(
    tmp_path: Path, knowledge: tuple[object, object, object]
) -> None:
    service, repository, _configuration = knowledge
    collection = service.create_collection("Status")  # type: ignore[attr-defined]
    source = tmp_path / "status.txt"
    source.write_text("Original local text.", encoding="utf-8")
    imported = service.import_document(source, collection)  # type: ignore[attr-defined]
    duplicate = service.import_document(source, collection)  # type: ignore[attr-defined]
    assert duplicate.duplicate
    assert len(repository.list_documents()) == 1  # type: ignore[attr-defined]

    source.write_text("Changed local text.", encoding="utf-8")
    assert service.list_sources()[0].status is KnowledgeSourceStatus.CHANGED  # type: ignore[attr-defined]
    with pytest.raises(DocumentImportError):
        service.import_document(source, collection)  # type: ignore[attr-defined]
    source.unlink()
    assert service.list_sources()[0].status is KnowledgeSourceStatus.MISSING  # type: ignore[attr-defined]
    assert repository.get_document(imported.document.document_id) is not None  # type: ignore[attr-defined]


def test_text_search_cites_safe_filename_and_line_range(
    tmp_path: Path, knowledge: tuple[object, object, object]
) -> None:
    service, _repository, _configuration = knowledge
    collection = service.create_collection("Lines")  # type: ignore[attr-defined]
    source = tmp_path / "lines.txt"
    source.write_text("first line\nneedle phrase\nthird line", encoding="utf-8")
    service.import_document(source, collection)  # type: ignore[attr-defined]
    hit = service.search(KnowledgeSearchQuery("needle phrase")).hits[0]  # type: ignore[attr-defined]
    assert hit.source.source_path_display == "lines.txt"
    assert hit.source.line_start == 1
    assert hit.source.line_end == 3
    assert "lines 1-3" in hit.source.label()


def test_directory_and_source_commands_use_existing_parser() -> None:
    parser = CommandParser()
    directory = parser.parse('Add the folder "C:\\Notes" to my knowledge base')
    sources = parser.parse("List my knowledge sources")
    mentions = parser.parse("Find documents mentioning gradient descent")
    assert directory.command.intent is IntentType.IMPORT_KNOWLEDGE_DIRECTORY
    assert any(item.name == "directory_path" for item in directory.command.entities)
    assert sources.command.intent is IntentType.LIST_KNOWLEDGE_SOURCES
    assert mentions.command.intent is IntentType.SEARCH_KNOWLEDGE


def test_safe_end_to_end_smoke_preserves_original_source(
    tmp_path: Path, knowledge: tuple[object, object, object]
) -> None:
    service, _repository, _configuration = knowledge
    collection = service.create_collection("Smoke")  # type: ignore[attr-defined]
    source = tmp_path / "smoke.txt"
    source.write_text("A distinctive local smoke phrase.", encoding="utf-8")
    imported = service.import_document(source, collection)  # type: ignore[attr-defined]
    result = service.search(KnowledgeSearchQuery("distinctive local smoke"))  # type: ignore[attr-defined]
    assert len(result.hits) == 1
    assert result.hits[0].source.source_path_display == "smoke.txt"
    removed = service.remove_document(  # type: ignore[attr-defined]
        imported.document.document_id, imported.document.revision
    )
    assert removed.source_file_preserved
    assert source.read_text(encoding="utf-8") == "A distinctive local smoke phrase."
