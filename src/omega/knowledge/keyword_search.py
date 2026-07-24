"""Deterministic bounded SQLite keyword retrieval."""

from __future__ import annotations

import re
import sqlite3
from uuid import UUID

from omega.knowledge.configuration import KnowledgeConfiguration
from omega.knowledge.enums import KnowledgeSearchMode
from omega.knowledge.models import (
    KnowledgeSearchHit,
    KnowledgeSearchQuery,
    KnowledgeSearchResult,
    KnowledgeSourceReference,
)
from omega.knowledge.repositories import KnowledgeRepository

_TOKEN = re.compile(r"[\w'-]+", re.UNICODE)
_STOPWORDS = frozenset(
    {
        "and",
        "are",
        "for",
        "from",
        "how",
        "into",
        "is",
        "of",
        "or",
        "that",
        "the",
        "this",
        "to",
        "what",
        "when",
        "where",
        "which",
        "who",
        "why",
        "with",
    }
)


class KeywordSearchService:
    """Rank bounded candidates without optional FTS or external services."""

    def __init__(
        self,
        configuration: KnowledgeConfiguration,
        repository: KnowledgeRepository,
    ) -> None:
        self.configuration = configuration
        self.repository = repository

    def search(self, query: KnowledgeSearchQuery) -> KnowledgeSearchResult:
        candidate_limit = min(
            self.configuration.maximum_search_limit * 10,
            max(query.limit * 10, query.limit),
        )
        rows = self.repository.keyword_candidates(
            query.text,
            collection_id=query.collection_id,
            document_id=query.document_id,
            source_type=query.file_type,
            limit=candidate_limit,
        )
        hits = tuple(
            sorted(
                (self._hit(row, query.text) for row in rows),
                key=lambda item: (
                    -item.score,
                    item.source.document_title.casefold(),
                    item.source.chunk_sequence,
                    str(item.chunk_id),
                ),
            )[: query.limit]
        )
        return KnowledgeSearchResult(query, hits)

    @staticmethod
    def _hit(row: sqlite3.Row, query: str) -> KnowledgeSearchHit:
        text = str(row["text"])
        folded = text.casefold()
        needle = query.casefold().strip()
        tokens = tuple(
            token
            for token in dict.fromkeys(_TOKEN.findall(needle))
            if len(token) > 2 and token not in _STOPWORDS
        )
        phrase = 1.0 if needle in folded else 0.0
        token_ratio = (
            sum(1 for token in tokens if token in folded) / len(tokens)
            if tokens
            else 0.0
        )
        title = str(row["document_title"]).casefold()
        title_bonus = 1.0 if needle in title else 0.0
        score = min(1.0, 0.55 * phrase + 0.35 * token_ratio + 0.10 * title_bonus)
        preview = KeywordSearchService._preview(text, needle)
        source = KnowledgeSourceReference(
            UUID(row["document_id"]),
            row["document_title"],
            row["collection_name"],
            int(row["sequence_number"]),
            preview,
            int(row["page_number"]) if row["page_number"] is not None else None,
            row["section_title"],
        )
        return KnowledgeSearchHit(
            UUID(row["chunk_id"]),
            score,
            source,
            text,
            KnowledgeSearchMode.KEYWORD,
        )

    @staticmethod
    def _preview(text: str, needle: str, maximum: int = 320) -> str:
        folded = text.casefold()
        position = folded.find(needle)
        start = max(0, position - maximum // 3) if position >= 0 else 0
        value = text[start : start + maximum].strip()
        return (
            ("…" if start else "")
            + value
            + ("…" if start + maximum < len(text) else "")
        )
