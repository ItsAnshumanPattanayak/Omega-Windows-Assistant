"""Stable local knowledge identifiers."""

from enum import StrEnum


class KnowledgeDocumentStatus(StrEnum):
    ACTIVE = "active"
    ARCHIVED = "archived"
    REMOVED = "removed"


class KnowledgeIndexStatus(StrEnum):
    PENDING = "pending"
    KEYWORD_READY = "keyword_ready"
    SEMANTIC_READY = "semantic_ready"
    SEMANTIC_UNAVAILABLE = "semantic_unavailable"
    FAILED = "failed"


class KnowledgeSearchMode(StrEnum):
    KEYWORD = "keyword"
    SEMANTIC = "semantic"
    HYBRID = "hybrid"


class KnowledgeSourceType(StrEnum):
    PDF = "pdf"
    DOCX = "docx"
    TEXT = "text"
    MARKDOWN = "markdown"


class ExtractionStatus(StrEnum):
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class KnowledgeExportFormat(StrEnum):
    JSON = "json"
    MARKDOWN = "markdown"
