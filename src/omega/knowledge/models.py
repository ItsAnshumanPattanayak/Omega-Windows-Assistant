"""Strict inert records for the local knowledge base."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID, uuid4

from omega.core.exceptions import ModelValidationError
from omega.knowledge.enums import (
    ExtractionStatus,
    KnowledgeDocumentStatus,
    KnowledgeExportFormat,
    KnowledgeIndexStatus,
    KnowledgeSearchMode,
    KnowledgeSourceType,
)
from omega.models._serialization import (
    JsonValue,
    serialize_value,
    utc_now,
    validate_json_mapping,
    validate_utc_timestamp,
)

_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def _text(value: str, name: str, maximum: int, *, empty: bool = False) -> str:
    if not isinstance(value, str):
        raise ModelValidationError(f"{name} must be text.")
    if not empty and not value.strip():
        raise ModelValidationError(f"{name} must not be empty.")
    if len(value) > maximum or _CONTROL.search(value):
        raise ModelValidationError(f"{name} is too long or contains controls.")
    return value


def _utc(value: datetime, name: str) -> datetime:
    return validate_utc_timestamp(value, name)


@dataclass(frozen=True)
class KnowledgeCollection:
    name: str
    description: str = ""
    collection_id: UUID = field(default_factory=uuid4)
    is_archived: bool = False
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)
    archived_at: datetime | None = None
    metadata: dict[str, JsonValue] = field(default_factory=dict)
    revision: int = 1

    def __post_init__(self) -> None:
        _text(self.name, "collection name", 120)
        _text(self.description, "collection description", 5_000, empty=True)
        object.__setattr__(self, "created_at", _utc(self.created_at, "created_at"))
        object.__setattr__(self, "updated_at", _utc(self.updated_at, "updated_at"))
        if self.archived_at is not None:
            object.__setattr__(
                self, "archived_at", _utc(self.archived_at, "archived_at")
            )
        if self.is_archived != (self.archived_at is not None):
            raise ModelValidationError("Archived collection state is inconsistent.")
        if self.revision < 1:
            raise ModelValidationError("revision must be positive.")
        object.__setattr__(
            self, "metadata", validate_json_mapping(self.metadata, "metadata")
        )

    def to_dict(self) -> dict[str, JsonValue]:
        return {
            "collection_id": str(self.collection_id),
            "name": self.name,
            "description": self.description,
            "is_archived": self.is_archived,
            "created_at": serialize_value(self.created_at),
            "updated_at": serialize_value(self.updated_at),
            "archived_at": serialize_value(self.archived_at),
            "metadata": self.metadata,
            "revision": self.revision,
        }


@dataclass(frozen=True)
class KnowledgeDocument:
    collection_id: UUID
    title: str
    original_filename: str
    source_path: str
    source_type: KnowledgeSourceType
    file_size_bytes: int
    content_fingerprint: str
    character_count: int
    document_id: UUID = field(default_factory=uuid4)
    status: KnowledgeDocumentStatus = KnowledgeDocumentStatus.ACTIVE
    extraction_status: ExtractionStatus = ExtractionStatus.SUCCEEDED
    index_status: KnowledgeIndexStatus = KnowledgeIndexStatus.KEYWORD_READY
    page_count: int | None = None
    imported_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)
    last_indexed_at: datetime | None = field(default_factory=utc_now)
    removed_at: datetime | None = None
    metadata: dict[str, JsonValue] = field(default_factory=dict)
    revision: int = 1

    def __post_init__(self) -> None:
        _text(self.title, "document title", 300)
        _text(self.original_filename, "original filename", 300)
        _text(self.source_path, "source path", 2_000)
        if self.file_size_bytes < 0 or self.character_count <= 0:
            raise ModelValidationError("Document sizes must be valid and non-empty.")
        if not re.fullmatch(r"[0-9a-f]{64}", self.content_fingerprint):
            raise ModelValidationError("Document fingerprint must be SHA-256.")
        if self.page_count is not None and self.page_count < 1:
            raise ModelValidationError("page_count must be positive.")
        if self.extraction_status is not ExtractionStatus.SUCCEEDED:
            raise ModelValidationError(
                "Stored active documents require extracted text."
            )
        if self.index_status is KnowledgeIndexStatus.PENDING:
            raise ModelValidationError(
                "Stored documents require a completed index state."
            )
        for name in ("imported_at", "updated_at"):
            object.__setattr__(self, name, _utc(getattr(self, name), name))
        if self.last_indexed_at is not None:
            object.__setattr__(
                self,
                "last_indexed_at",
                _utc(self.last_indexed_at, "last_indexed_at"),
            )
        if self.removed_at is not None:
            object.__setattr__(self, "removed_at", _utc(self.removed_at, "removed_at"))
        if (self.status is KnowledgeDocumentStatus.REMOVED) != (
            self.removed_at is not None
        ):
            raise ModelValidationError("Removed document state is inconsistent.")
        if self.revision < 1:
            raise ModelValidationError("revision must be positive.")
        object.__setattr__(
            self, "metadata", validate_json_mapping(self.metadata, "metadata")
        )

    def to_dict(self, *, include_source_path: bool = False) -> dict[str, JsonValue]:
        return {
            "document_id": str(self.document_id),
            "collection_id": str(self.collection_id),
            "title": self.title,
            "original_filename": self.original_filename,
            "source_path": self.source_path if include_source_path else None,
            "source_type": self.source_type.value,
            "file_size_bytes": self.file_size_bytes,
            "content_fingerprint": self.content_fingerprint,
            "character_count": self.character_count,
            "status": self.status.value,
            "extraction_status": self.extraction_status.value,
            "index_status": self.index_status.value,
            "page_count": self.page_count,
            "imported_at": serialize_value(self.imported_at),
            "updated_at": serialize_value(self.updated_at),
            "last_indexed_at": serialize_value(self.last_indexed_at),
            "removed_at": serialize_value(self.removed_at),
            "metadata": self.metadata,
            "revision": self.revision,
        }


@dataclass(frozen=True)
class ExtractedSegment:
    text: str
    page_number: int | None = None
    section_title: str | None = None

    def __post_init__(self) -> None:
        _text(self.text, "segment text", 2_000_000)
        if self.page_number is not None and self.page_number < 1:
            raise ModelValidationError("page_number must be positive.")
        if self.section_title is not None:
            _text(self.section_title, "section title", 300)


@dataclass(frozen=True)
class DocumentExtractionResult:
    title: str
    text: str
    source_filename: str
    source_type: KnowledgeSourceType
    content_fingerprint: str
    extractor_name: str
    segments: tuple[ExtractedSegment, ...]
    extracted_at: datetime = field(default_factory=utc_now)
    page_count: int | None = None
    section_count: int | None = None
    warnings: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _text(self.title, "extracted title", 300)
        _text(self.text, "extracted text", 2_000_000)
        _text(self.source_filename, "source filename", 300)
        _text(self.extractor_name, "extractor name", 100)
        if not self.segments or not any(item.text.strip() for item in self.segments):
            raise ModelValidationError("Successful extraction requires text segments.")
        if self.text != "\n\n".join(item.text for item in self.segments):
            raise ModelValidationError("Extraction text must match ordered segments.")
        if not re.fullmatch(r"[0-9a-f]{64}", self.content_fingerprint):
            raise ModelValidationError("Extraction fingerprint must be SHA-256.")
        object.__setattr__(
            self, "extracted_at", _utc(self.extracted_at, "extracted_at")
        )


@dataclass(frozen=True)
class KnowledgeChunk:
    document_id: UUID
    sequence_number: int
    text: str
    text_hash: str
    character_start: int
    character_end: int
    chunk_id: UUID = field(default_factory=uuid4)
    page_number: int | None = None
    section_title: str | None = None
    token_estimate: int = 0
    created_at: datetime = field(default_factory=utc_now)
    metadata: dict[str, JsonValue] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.sequence_number < 0:
            raise ModelValidationError("sequence_number must be non-negative.")
        _text(self.text, "chunk text", 20_000)
        if not re.fullmatch(r"[0-9a-f]{64}", self.text_hash):
            raise ModelValidationError("Chunk hash must be SHA-256.")
        if self.character_start < 0 or self.character_end <= self.character_start:
            raise ModelValidationError("Chunk character offsets are invalid.")
        if self.page_number is not None and self.page_number < 1:
            raise ModelValidationError("page_number must be positive.")
        if self.section_title is not None:
            _text(self.section_title, "section title", 300)
        if self.token_estimate < 1:
            object.__setattr__(self, "token_estimate", max(1, len(self.text) // 4))
        object.__setattr__(self, "created_at", _utc(self.created_at, "created_at"))
        object.__setattr__(
            self, "metadata", validate_json_mapping(self.metadata, "metadata")
        )


@dataclass(frozen=True)
class KnowledgeSearchQuery:
    text: str
    mode: KnowledgeSearchMode = KnowledgeSearchMode.KEYWORD
    collection_id: UUID | None = None
    document_id: UUID | None = None
    file_type: KnowledgeSourceType | None = None
    limit: int = 10

    def __post_init__(self) -> None:
        _text(self.text, "knowledge query", 1_000)
        if not 1 <= self.limit <= 100:
            raise ModelValidationError("Knowledge search limit must be 1 through 100.")


@dataclass(frozen=True)
class KnowledgeSourceReference:
    document_id: UUID
    document_title: str
    collection_name: str
    chunk_sequence: int
    preview: str
    page_number: int | None = None
    section_title: str | None = None

    def __post_init__(self) -> None:
        _text(self.document_title, "document title", 300)
        _text(self.collection_name, "collection name", 120)
        _text(self.preview, "source preview", 1_000)
        if self.chunk_sequence < 0:
            raise ModelValidationError("chunk_sequence must be non-negative.")

    def label(self) -> str:
        location = (
            f"page {self.page_number}"
            if self.page_number is not None
            else (
                self.section_title
                if self.section_title is not None
                else f"chunk {self.chunk_sequence + 1}"
            )
        )
        return f"{self.document_title} ({location})"


@dataclass(frozen=True)
class KnowledgeSearchHit:
    chunk_id: UUID
    score: float
    source: KnowledgeSourceReference
    text: str
    mode: KnowledgeSearchMode = KnowledgeSearchMode.KEYWORD

    def __post_init__(self) -> None:
        if isinstance(self.score, bool) or not 0.0 <= self.score <= 1.0:
            raise ModelValidationError("Search score must be within 0 and 1.")
        _text(self.text, "search hit text", 20_000)


@dataclass(frozen=True)
class KnowledgeSearchResult:
    query: KnowledgeSearchQuery
    hits: tuple[KnowledgeSearchHit, ...]
    semantic_fallback: bool = False


@dataclass(frozen=True)
class KnowledgeAnswer:
    question: str
    answer: str
    sources: tuple[KnowledgeSourceReference, ...]
    supported: bool

    def __post_init__(self) -> None:
        _text(self.question, "knowledge question", 1_000)
        _text(self.answer, "knowledge answer", 20_000)
        if self.supported and not self.sources:
            raise ModelValidationError("Supported answers require source references.")


@dataclass(frozen=True)
class DocumentImportResult:
    document: KnowledgeDocument
    chunks_created: int
    duplicate: bool = False
    semantic_available: bool = False


@dataclass(frozen=True)
class DocumentReindexResult:
    document: KnowledgeDocument
    chunks_replaced: int
    changed: bool


@dataclass(frozen=True)
class KnowledgeRemovalResult:
    document_id: UUID
    chunks_removed: int
    source_file_preserved: bool = True


@dataclass(frozen=True)
class KnowledgeExportResult:
    path: str
    format: KnowledgeExportFormat
    item_count: int
    bytes_written: int
