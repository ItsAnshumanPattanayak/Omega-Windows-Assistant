"""Explicit optional semantic-search boundary with keyword-safe fallback."""

from __future__ import annotations

from uuid import UUID

from omega.knowledge.models import (
    KnowledgeChunk,
    KnowledgeSearchHit,
    KnowledgeSearchQuery,
)


class UnavailableSemanticSearch:
    """No-op adapter used when no explicit local model implementation is installed."""

    @property
    def available(self) -> bool:
        return False

    @property
    def model_identifier(self) -> str | None:
        return None

    def index(self, document_id: UUID, chunks: tuple[KnowledgeChunk, ...]) -> None:
        return None

    def remove(self, document_id: UUID) -> None:
        return None

    def search(self, query: KnowledgeSearchQuery) -> tuple[KnowledgeSearchHit, ...]:
        return ()
