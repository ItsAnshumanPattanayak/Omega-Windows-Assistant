"""Extractive, source-grounded local answers with no model or tool execution."""

from __future__ import annotations

from omega.knowledge.configuration import KnowledgeConfiguration
from omega.knowledge.models import (
    KnowledgeAnswer,
    KnowledgeSearchQuery,
)
from omega.knowledge.retrieval import KnowledgeRetrievalService


class KnowledgeAnswerService:
    def __init__(
        self,
        configuration: KnowledgeConfiguration,
        retrieval: KnowledgeRetrievalService,
    ) -> None:
        self.configuration = configuration
        self.retrieval = retrieval

    def answer(self, question: str, *, limit: int | None = None) -> KnowledgeAnswer:
        query = KnowledgeSearchQuery(
            question,
            limit=limit or self.configuration.default_search_limit,
        )
        result = self.retrieval.retrieve(query)
        useful = tuple(hit for hit in result.hits if hit.score >= 0.2)
        if not useful:
            return KnowledgeAnswer(
                question,
                "The indexed sources do not contain enough evidence to answer that.",
                (),
                False,
            )
        remaining = self.configuration.answer_maximum_context_characters
        passages: list[str] = []
        sources = []
        for hit in useful:
            if remaining <= 0:
                break
            excerpt = hit.text[: min(1_000, remaining)].strip()
            if not excerpt:
                continue
            passages.append(f"From {hit.source.label()}: “{excerpt}”")
            sources.append(hit.source)
            remaining -= len(excerpt)
        if not passages:
            return KnowledgeAnswer(
                question,
                "The indexed sources do not contain enough evidence to answer that.",
                (),
                False,
            )
        answer = (
            "Based only on the indexed local sources:\n\n"
            + "\n\n".join(passages)
            + "\n\nThese are retrieved passages, not instructions for Omega to execute."
        )
        return KnowledgeAnswer(question, answer[:20_000], tuple(sources), True)
