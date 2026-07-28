"""Proposal-only adapters for existing Omega domains."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from omega.ai.exceptions import (
    AiDisabledError,
    AiError,
    AiPermissionError,
    AiValidationError,
)
from omega.ai.models import (
    AiContextItem,
    AiContextKind,
    AiEmbeddingResult,
    AiGenerationResult,
)
from omega.ai.service import AiService
from omega.knowledge.models import (
    KnowledgeAnswer,
    KnowledgeSearchQuery,
    KnowledgeSearchResult,
)


@dataclass(frozen=True)
class AiDraftProposal:
    domain: str
    original_text: str
    proposed_text: str
    generated: bool
    warning: str
    applied: bool = False


class AiProposalService:
    """Create inert drafts without receiving any mutation-capable service."""

    def __init__(self, ai: AiService) -> None:
        self.ai = ai

    def email_draft(
        self, text: str, instruction: str = "Improve this draft"
    ) -> AiDraftProposal:
        return self._proposal("email", "email_draft", text, instruction)

    def calendar_description(
        self, text: str, instruction: str = "Improve this event description"
    ) -> AiDraftProposal:
        return self._proposal("calendar", "calendar_description", text, instruction)

    def note_rewrite(
        self, text: str, instruction: str = "Rewrite this note"
    ) -> AiDraftProposal:
        return self._proposal("note", "note_rewrite", text, instruction)

    def task_suggestions(self, text: str) -> AiDraftProposal:
        return self._proposal("task", "task_suggestions", text, "Suggest tasks")

    def _proposal(
        self, domain: str, task: str, text: str, instruction: str
    ) -> AiDraftProposal:
        if not text.strip():
            raise AiValidationError("Source text must not be empty.")
        enabled = {
            "email": self.ai.configuration.enable_email_assistance,
            "calendar": self.ai.configuration.enable_calendar_assistance,
            "note": self.ai.configuration.enable_note_assistance,
            "task": self.ai.configuration.enable_note_assistance,
        }[domain]
        if not enabled:
            raise AiDisabledError(f"Local AI {domain} assistance is disabled.")
        kind = {
            "email": AiContextKind.EMAIL,
            "calendar": AiContextKind.CALENDAR,
            "note": AiContextKind.NOTE,
            "task": AiContextKind.NOTE,
        }[domain]
        result = self.ai.generate(
            task,
            instruction,
            context=(AiContextItem(f"selected-{domain}", kind, text),),
        )
        return AiDraftProposal(
            domain, text, result.text, result.generated, result.warning, False
        )


class PluginAiAccess:
    """Permission- and quota-bound façade for reviewed plugins."""

    def __init__(
        self,
        ai: AiService,
        permission_checker: Callable[[str, str, str, str], None],
        *,
        maximum_requests_per_session: int = 10,
    ) -> None:
        if maximum_requests_per_session <= 0:
            raise AiValidationError("Plugin AI quota must be positive.")
        self.ai = ai
        self.permission_checker = permission_checker
        self.maximum_requests_per_session = maximum_requests_per_session
        self._usage: dict[tuple[str, UUID], int] = {}

    def generate(
        self,
        plugin_id: str,
        plugin_version: str,
        plugin_fingerprint: str,
        session_id: UUID,
        text: str,
    ) -> AiGenerationResult:
        try:
            self.permission_checker(
                plugin_id,
                plugin_version,
                plugin_fingerprint,
                "use_local_ai_generation",
            )
        except Exception as error:
            raise AiPermissionError(
                "Plugin local-AI generation is not approved."
            ) from error
        key = (plugin_id, session_id)
        used = self._usage.get(key, 0)
        if used >= self.maximum_requests_per_session:
            raise AiPermissionError("The plugin local-AI quota was reached.")
        self._usage[key] = used + 1
        context = (AiContextItem(plugin_id, AiContextKind.PLUGIN, text),)
        return self.ai.generate(
            "plugin_generation",
            "Generate bounded text from plugin data",
            context=context,
        )

    def clear_session(self, session_id: UUID) -> None:
        self._usage = {
            key: value for key, value in self._usage.items() if key[1] != session_id
        }

    def embeddings(
        self,
        plugin_id: str,
        plugin_version: str,
        plugin_fingerprint: str,
        session_id: UUID,
        texts: tuple[str, ...],
    ) -> AiEmbeddingResult:
        try:
            self.permission_checker(
                plugin_id,
                plugin_version,
                plugin_fingerprint,
                "use_local_ai_embeddings",
            )
        except Exception as error:
            raise AiPermissionError(
                "Plugin local-AI embeddings are not approved."
            ) from error
        key = (plugin_id, session_id)
        used = self._usage.get(key, 0)
        if used >= self.maximum_requests_per_session:
            raise AiPermissionError("The plugin local-AI quota was reached.")
        self._usage[key] = used + 1
        return self.ai.embeddings(texts)


class KnowledgeAssistantSource(Protocol):
    def search(self, query: KnowledgeSearchQuery) -> KnowledgeSearchResult: ...

    def answer(self, question: str) -> KnowledgeAnswer: ...


class AiKnowledgeAssistant:
    """Retrieve through Phase 17 before optional citation-checked generation."""

    def __init__(self, ai: AiService, knowledge: KnowledgeAssistantSource) -> None:
        self.ai = ai
        self.knowledge = knowledge

    def answer(self, question: str) -> AiGenerationResult:
        if not self.ai.configuration.enabled:
            fallback = self.knowledge.answer(question)
            return AiGenerationResult(
                "deterministic-knowledge",
                None,
                fallback.answer,
                False,
                "Local AI is unavailable. Omega used the cited extractive answer.",
                citations=tuple(str(item.document_id) for item in fallback.sources),
            )
        result = self.knowledge.search(
            KnowledgeSearchQuery(
                question,
                limit=self.ai.configuration.maximum_grounding_chunks,
            )
        )
        contexts = tuple(
            AiContextItem(
                str(hit.chunk_id),
                AiContextKind.KNOWLEDGE,
                hit.text,
                location=hit.source.label(),
            )
            for hit in result.hits
        )
        if not contexts:
            fallback = self.knowledge.answer(question)
            return AiGenerationResult(
                "unsupported-knowledge",
                None,
                fallback.answer,
                False,
                "The indexed sources do not support a local-AI answer.",
            )
        try:
            return self.ai.grounded_answer(question, contexts)
        except AiError:
            fallback = self.knowledge.answer(question)
            return AiGenerationResult(
                "deterministic-knowledge",
                None,
                fallback.answer,
                False,
                "Local AI failed safely. Omega used the extractive answer instead.",
                citations=tuple(str(item.document_id) for item in fallback.sources),
            )
