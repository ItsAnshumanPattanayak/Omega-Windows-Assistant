"""Narrow failures for Omega's local knowledge boundary."""

from omega.core.exceptions import OmegaError


class KnowledgeError(OmegaError):
    """Base failure for local knowledge operations."""


class KnowledgeConfigurationError(KnowledgeError):
    """Raised when trusted knowledge configuration fails closed."""


class UnsupportedDocumentError(KnowledgeError):
    """Raised for a document format Omega cannot safely extract."""


class DocumentValidationError(KnowledgeError):
    """Raised when an explicitly selected source file is unsafe."""


class DocumentExtractionError(KnowledgeError):
    """Raised when bounded text extraction cannot produce usable text."""


class DocumentImportError(KnowledgeError):
    """Raised when an import cannot be completed atomically."""


class DocumentNotFoundError(KnowledgeError):
    """Raised when an active document cannot be resolved uniquely."""


class KnowledgeCollectionNotFoundError(KnowledgeError):
    """Raised when an active collection cannot be resolved uniquely."""


class KnowledgeIndexError(KnowledgeError):
    """Raised when a local index cannot be built safely."""


class KnowledgeSearchError(KnowledgeError):
    """Raised when a bounded local query is invalid."""


class KnowledgeAnswerError(KnowledgeError):
    """Raised when a grounded answer request is invalid."""


class KnowledgeConflictError(KnowledgeError):
    """Raised for duplicate names, fingerprints, or non-empty deletion."""


class StaleKnowledgeRevisionError(KnowledgeConflictError):
    """Raised when optimistic revision validation detects a stale mutation."""
