"""Public local knowledge API; importing this package has no side effects."""

from omega.knowledge.answering import KnowledgeAnswerService
from omega.knowledge.chunking import DeterministicChunker
from omega.knowledge.configuration import KnowledgeConfiguration
from omega.knowledge.enums import (
    ExtractionStatus,
    KnowledgeDocumentStatus,
    KnowledgeExportFormat,
    KnowledgeIndexStatus,
    KnowledgeSearchMode,
    KnowledgeSourceStatus,
    KnowledgeSourceType,
)
from omega.knowledge.models import (
    DirectoryImportResult,
    DocumentExtractionResult,
    DocumentImportResult,
    DocumentReindexResult,
    ExtractedSegment,
    KnowledgeAnswer,
    KnowledgeChunk,
    KnowledgeCollection,
    KnowledgeDocument,
    KnowledgeExportResult,
    KnowledgeRemovalResult,
    KnowledgeSearchHit,
    KnowledgeSearchQuery,
    KnowledgeSearchResult,
    KnowledgeSourceReference,
    KnowledgeSourceView,
)
from omega.knowledge.repositories import KnowledgeRepository
from omega.knowledge.service import KnowledgeService

__all__ = [
    "DeterministicChunker",
    "DocumentExtractionResult",
    "DocumentImportResult",
    "DocumentReindexResult",
    "DirectoryImportResult",
    "ExtractedSegment",
    "ExtractionStatus",
    "KnowledgeAnswer",
    "KnowledgeAnswerService",
    "KnowledgeChunk",
    "KnowledgeCollection",
    "KnowledgeConfiguration",
    "KnowledgeDocument",
    "KnowledgeDocumentStatus",
    "KnowledgeExportFormat",
    "KnowledgeExportResult",
    "KnowledgeIndexStatus",
    "KnowledgeRemovalResult",
    "KnowledgeRepository",
    "KnowledgeSearchHit",
    "KnowledgeSearchMode",
    "KnowledgeSearchQuery",
    "KnowledgeSearchResult",
    "KnowledgeService",
    "KnowledgeSourceReference",
    "KnowledgeSourceStatus",
    "KnowledgeSourceType",
    "KnowledgeSourceView",
]
