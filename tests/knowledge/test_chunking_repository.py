from dataclasses import replace
from pathlib import Path
from uuid import uuid4

import pytest

from omega.knowledge import (
    DeterministicChunker,
    DocumentExtractionResult,
    ExtractedSegment,
    KnowledgeConfiguration,
    KnowledgeSourceType,
)
from omega.knowledge.exceptions import (
    KnowledgeConflictError,
    StaleKnowledgeRevisionError,
)
from tests.knowledge.conftest import write_pdf


def test_chunking_is_deterministic_overlapping_and_bounded() -> None:
    configuration = KnowledgeConfiguration(
        chunk_size_characters=100, chunk_overlap_characters=20
    )
    collection = uuid4()
    extracted_text = ("word " * 80).strip()
    extraction = DocumentExtractionResult(
        "Title",
        extracted_text,
        "sample.txt",
        KnowledgeSourceType.TEXT,
        "0" * 64,
        "test",
        (ExtractedSegment(extracted_text, section_title="Section"),),
    )
    first = DeterministicChunker(configuration).chunk(collection, extraction)
    second = DeterministicChunker(configuration).chunk(collection, extraction)
    assert [item.chunk_id for item in first] == [item.chunk_id for item in second]
    assert [item.sequence_number for item in first] == list(range(len(first)))
    assert all(item.section_title == "Section" for item in first)
    assert all(item.text for item in first)


def test_collection_document_repository_and_revision_safety(
    tmp_path: Path,
    knowledge: tuple[object, object, object],
) -> None:
    service, repository, _configuration = knowledge
    collection = service.create_collection("College Notes")  # type: ignore[attr-defined]
    with pytest.raises(KnowledgeConflictError):
        service.create_collection("college notes")  # type: ignore[attr-defined]
    path = tmp_path / "lesson.pdf"
    write_pdf(path)
    imported = service.import_document(path, collection)  # type: ignore[attr-defined]
    stored = repository.get_document(imported.document.document_id)  # type: ignore[attr-defined]
    assert stored is not None
    assert repository.chunks_for_document(stored.document_id)  # type: ignore[attr-defined]
    with pytest.raises(StaleKnowledgeRevisionError):
        repository.update_document(  # type: ignore[attr-defined]
            replace(stored, revision=stored.revision + 1),
            stored.revision - 1,
        )
    with pytest.raises(KnowledgeConflictError):
        service.delete_collection(  # type: ignore[attr-defined]
            collection.collection_id, collection.revision
        )
