"""Bounded deterministic merge of keyword and optional local semantic results."""

from __future__ import annotations

from omega.knowledge.configuration import KnowledgeConfiguration
from omega.knowledge.enums import KnowledgeSearchMode
from omega.knowledge.keyword_search import KeywordSearchService
from omega.knowledge.models import (
    KnowledgeSearchHit,
    KnowledgeSearchQuery,
    KnowledgeSearchResult,
)
from omega.knowledge.protocols import SemanticSearchProvider


class KnowledgeRetrievalService:
    def __init__(
        self,
        configuration: KnowledgeConfiguration,
        keyword: KeywordSearchService,
        semantic: SemanticSearchProvider,
    ) -> None:
        self.configuration = configuration
        self.keyword = keyword
        self.semantic = semantic

    def retrieve(self, query: KnowledgeSearchQuery) -> KnowledgeSearchResult:
        keyword_result = self.keyword.search(query)
        if query.mode is KnowledgeSearchMode.KEYWORD:
            return keyword_result
        if (
            not self.configuration.semantic_search_enabled
            or not self.semantic.available
        ):
            return KnowledgeSearchResult(
                query, keyword_result.hits, semantic_fallback=True
            )
        semantic_hits = self.semantic.search(query)
        if query.mode is KnowledgeSearchMode.SEMANTIC:
            selected = semantic_hits
        else:
            selected = self._merge(keyword_result.hits, semantic_hits, query.limit)
        return KnowledgeSearchResult(query, selected[: query.limit])

    @staticmethod
    def _merge(
        keyword: tuple[KnowledgeSearchHit, ...],
        semantic: tuple[KnowledgeSearchHit, ...],
        limit: int,
    ) -> tuple[KnowledgeSearchHit, ...]:
        best: dict[object, KnowledgeSearchHit] = {}
        for item in (*keyword, *semantic):
            existing = best.get(item.chunk_id)
            if existing is None or item.score > existing.score:
                best[item.chunk_id] = item
        ordered = sorted(
            best.values(),
            key=lambda item: (
                -item.score,
                item.source.document_title.casefold(),
                item.source.chunk_sequence,
            ),
        )
        diversified: list[KnowledgeSearchHit] = []
        per_document: dict[object, int] = {}
        for item in ordered:
            count = per_document.get(item.source.document_id, 0)
            if count >= max(2, limit // 2):
                continue
            diversified.append(item)
            per_document[item.source.document_id] = count + 1
            if len(diversified) == limit:
                break
        return tuple(diversified)
