"""Application-facing local knowledge orchestration."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

from omega.knowledge.answering import KnowledgeAnswerService
from omega.knowledge.chunking import DeterministicChunker
from omega.knowledge.configuration import KnowledgeConfiguration
from omega.knowledge.enums import (
    KnowledgeDocumentStatus,
    KnowledgeIndexStatus,
)
from omega.knowledge.exceptions import (
    DocumentImportError,
    DocumentNotFoundError,
    KnowledgeCollectionNotFoundError,
    KnowledgeConflictError,
    StaleKnowledgeRevisionError,
)
from omega.knowledge.extractors import ExtractorRegistry
from omega.knowledge.keyword_search import KeywordSearchService
from omega.knowledge.models import (
    DocumentImportResult,
    DocumentReindexResult,
    KnowledgeAnswer,
    KnowledgeCollection,
    KnowledgeDocument,
    KnowledgeRemovalResult,
    KnowledgeSearchQuery,
    KnowledgeSearchResult,
)
from omega.knowledge.protocols import SemanticSearchProvider
from omega.knowledge.repositories import KnowledgeRepository
from omega.knowledge.retrieval import KnowledgeRetrievalService
from omega.knowledge.validation import KnowledgeFileValidator
from omega.models._serialization import utc_now


class KnowledgeService:
    """Coordinate only explicit, validated local knowledge operations."""

    def __init__(
        self,
        configuration: KnowledgeConfiguration,
        repository: KnowledgeRepository,
        validator: KnowledgeFileValidator,
        extractors: ExtractorRegistry,
        chunker: DeterministicChunker,
        semantic: SemanticSearchProvider,
    ) -> None:
        self.configuration = configuration
        self.repository = repository
        self.validator = validator
        self.extractors = extractors
        self.chunker = chunker
        self.semantic = semantic
        self.keyword = KeywordSearchService(configuration, repository)
        self.retrieval = KnowledgeRetrievalService(
            configuration, self.keyword, semantic
        )
        self.answers = KnowledgeAnswerService(configuration, self.retrieval)

    def create_collection(
        self, name: str, description: str = ""
    ) -> KnowledgeCollection:
        if self.repository.collection_count() >= self.configuration.maximum_collections:
            raise KnowledgeConflictError("The collection limit has been reached.")
        return self.repository.add_collection(KnowledgeCollection(name, description))

    def ensure_default_collection(self) -> KnowledgeCollection:
        try:
            return self.repository.resolve_collection("General")
        except KnowledgeCollectionNotFoundError:
            return self.create_collection(
                "General", "Default local knowledge collection."
            )

    def list_collections(self) -> tuple[KnowledgeCollection, ...]:
        return self.repository.list_collections()

    def update_collection(
        self,
        collection_id: UUID,
        revision: int,
        *,
        name: str | None = None,
        description: str | None = None,
        archived: bool | None = None,
    ) -> KnowledgeCollection:
        item = self.repository.get_collection(collection_id)
        if item is None:
            raise KnowledgeConflictError("The collection no longer exists.")
        if item.revision != revision:
            raise StaleKnowledgeRevisionError("The collection revision is stale.")
        now = utc_now()
        value = replace(
            item,
            name=item.name if name is None else name,
            description=item.description if description is None else description,
            is_archived=item.is_archived if archived is None else archived,
            archived_at=(
                item.archived_at if archived is None else now if archived else None
            ),
            updated_at=now,
            revision=item.revision + 1,
        )
        return self.repository.update_collection(value, revision)

    def delete_collection(
        self, collection_id: UUID, revision: int, *, include_documents: bool = False
    ) -> int:
        return self.repository.delete_collection(
            collection_id, revision, include_documents=include_documents
        )

    def import_document(
        self,
        path: Path,
        collection: KnowledgeCollection,
        *,
        title: str | None = None,
    ) -> DocumentImportResult:
        if not self.configuration.enabled:
            raise DocumentImportError("The local knowledge feature is disabled.")
        if self.repository.document_count() >= self.configuration.maximum_documents:
            raise DocumentImportError("The document limit has been reached.")
        validated = self.validator.validate(path)
        duplicate = self.repository.find_by_fingerprint(validated.fingerprint)
        if duplicate is not None and not self.configuration.allow_duplicate_content:
            return DocumentImportResult(
                duplicate,
                len(self.repository.chunks_for_document(duplicate.document_id)),
                duplicate=True,
                semantic_available=self.semantic.available,
            )
        extractor = self.extractors.require(validated.source_type)
        extraction = extractor.extract(validated.path, validated.fingerprint)
        document = KnowledgeDocument(
            collection.collection_id,
            (title or extraction.title)[
                : self.configuration.maximum_document_title_characters
            ],
            validated.path.name,
            str(validated.path),
            validated.source_type,
            validated.size_bytes,
            validated.fingerprint,
            len(extraction.text),
            page_count=extraction.page_count,
            index_status=(
                KnowledgeIndexStatus.KEYWORD_READY
                if self.semantic.available
                else KnowledgeIndexStatus.SEMANTIC_UNAVAILABLE
            ),
            metadata={
                "extractor": extraction.extractor_name,
                "section_count": extraction.section_count,
                "warnings": list(extraction.warnings),
                "document_content_is_untrusted_data": True,
            },
        )
        chunks = self.chunker.chunk(document.document_id, extraction)
        self.repository.add_document_with_chunks(document, chunks)
        if self.semantic.available:
            try:
                self.semantic.index(document.document_id, chunks)
            except Exception:
                return DocumentImportResult(document, len(chunks), False, False)
            semantic_document = replace(
                document,
                index_status=KnowledgeIndexStatus.SEMANTIC_READY,
                updated_at=utc_now(),
                revision=document.revision + 1,
            )
            document = self.repository.update_document(
                semantic_document, document.revision
            )
        return DocumentImportResult(
            document, len(chunks), False, self.semantic.available
        )

    def list_documents(
        self, collection_id: UUID | None = None
    ) -> tuple[KnowledgeDocument, ...]:
        return self.repository.list_documents(collection_id=collection_id)

    def move_document(
        self,
        document_id: UUID,
        revision: int,
        collection_id: UUID,
    ) -> KnowledgeDocument:
        item = self._document(document_id, revision)
        if self.repository.get_collection(collection_id) is None:
            raise KnowledgeConflictError("The destination collection does not exist.")
        value = replace(
            item,
            collection_id=collection_id,
            updated_at=utc_now(),
            revision=item.revision + 1,
        )
        return self.repository.update_document(value, revision)

    def reindex_document(
        self, document_id: UUID, revision: int
    ) -> DocumentReindexResult:
        item = self._document(document_id, revision)
        validated = self.validator.validate(Path(item.source_path))
        if validated.fingerprint == item.content_fingerprint:
            return DocumentReindexResult(
                item, len(self.repository.chunks_for_document(item.document_id)), False
            )
        extraction = self.extractors.require(validated.source_type).extract(
            validated.path, validated.fingerprint
        )
        chunks = self.chunker.chunk(item.document_id, extraction)
        now = utc_now()
        replacement = replace(
            item,
            title=extraction.title,
            original_filename=validated.path.name,
            source_path=str(validated.path),
            source_type=validated.source_type,
            file_size_bytes=validated.size_bytes,
            content_fingerprint=validated.fingerprint,
            character_count=len(extraction.text),
            page_count=extraction.page_count,
            index_status=(
                KnowledgeIndexStatus.KEYWORD_READY
                if self.semantic.available
                else KnowledgeIndexStatus.SEMANTIC_UNAVAILABLE
            ),
            updated_at=now,
            last_indexed_at=now,
            revision=item.revision + 1,
        )
        self.repository.replace_document_and_chunks(replacement, revision, chunks)
        if self.semantic.available:
            try:
                self.semantic.remove(item.document_id)
                self.semantic.index(item.document_id, chunks)
            except Exception:
                return DocumentReindexResult(replacement, len(chunks), True)
            semantic_document = replace(
                replacement,
                index_status=KnowledgeIndexStatus.SEMANTIC_READY,
                updated_at=utc_now(),
                revision=replacement.revision + 1,
            )
            replacement = self.repository.update_document(
                semantic_document, replacement.revision
            )
        return DocumentReindexResult(replacement, len(chunks), True)

    def remove_document(
        self, document_id: UUID, revision: int
    ) -> KnowledgeRemovalResult:
        item = self._document(document_id, revision)
        now = datetime.now(UTC)
        removed = replace(
            item,
            status=KnowledgeDocumentStatus.REMOVED,
            removed_at=now,
            updated_at=now,
            index_status=KnowledgeIndexStatus.FAILED,
            revision=item.revision + 1,
        )
        self.semantic.remove(document_id)
        chunks = self.repository.remove_document(removed, revision)
        return KnowledgeRemovalResult(document_id, chunks, True)

    def search(self, query: KnowledgeSearchQuery) -> KnowledgeSearchResult:
        return self.retrieval.retrieve(query)

    def answer(self, question: str) -> KnowledgeAnswer:
        return self.answers.answer(question)

    def _document(self, document_id: UUID, revision: int) -> KnowledgeDocument:
        item = self.repository.get_document(document_id)
        if item is None:
            raise DocumentNotFoundError("The document no longer exists.")
        if item.revision != revision:
            raise StaleKnowledgeRevisionError("The document revision is stale.")
        return item
