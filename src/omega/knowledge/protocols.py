"""Protocols for explicitly initialized local knowledge components."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol
from uuid import UUID

from omega.knowledge.models import (
    DocumentExtractionResult,
    KnowledgeChunk,
    KnowledgeSearchHit,
    KnowledgeSearchQuery,
)


class DocumentExtractor(Protocol):
    name: str

    def extract(self, path: Path, fingerprint: str) -> DocumentExtractionResult: ...


class SemanticSearchProvider(Protocol):
    """Optional local-only semantic adapter; implementations never download models."""

    @property
    def available(self) -> bool: ...

    @property
    def model_identifier(self) -> str | None: ...

    def index(self, document_id: UUID, chunks: tuple[KnowledgeChunk, ...]) -> None: ...

    def remove(self, document_id: UUID) -> None: ...

    def search(self, query: KnowledgeSearchQuery) -> tuple[KnowledgeSearchHit, ...]: ...
