"""Single controlled service boundary for all optional AI behavior."""

from __future__ import annotations

from threading import RLock
from uuid import UUID

from omega.ai.configuration import AiConfiguration
from omega.ai.exceptions import (
    AiDisabledError,
    AiError,
    AiModelError,
    AiValidationError,
)
from omega.ai.models import (
    AiContextItem,
    AiContextKind,
    AiEmbeddingRequest,
    AiEmbeddingResult,
    AiGenerationRequest,
    AiGenerationResult,
    AiGroundingSource,
    AiModelCapability,
    AiModelDescriptor,
    AiProviderStatus,
)
from omega.ai.prompt import AiPromptBuilder
from omega.ai.registry import AiModelRegistry
from omega.ai.resource import AiResourceManager
from omega.ai.validation import AiResponseValidator
from omega.models._serialization import JsonValue

_WARNING = "AI-generated text may be incorrect. Review it before use."


class AiService:
    """Generate proposals only; this class has no tool or domain mutation access."""

    def __init__(
        self,
        configuration: AiConfiguration,
        models: AiModelRegistry,
        resources: AiResourceManager,
    ) -> None:
        self.configuration = configuration
        self.models = models
        self.resources = resources
        self.prompts = AiPromptBuilder(configuration)
        self.validator = AiResponseValidator(configuration.maximum_response_characters)
        self._contexts: dict[UUID, list[AiContextItem]] = {}
        self._lock = RLock()

    def status(self) -> AiProviderStatus:
        status = self.resources.status(self.configuration.provider)
        if not self.configuration.enabled:
            return AiProviderStatus(
                False,
                self.configuration.provider,
                (),
                status.active_requests,
                status.queued_requests,
                "Local AI is disabled; deterministic Omega features remain available.",
            )
        return status

    def list_models(self) -> tuple[AiModelDescriptor, ...]:
        return self.models.list()

    def load_model(self, model_id: str) -> None:
        self._require_enabled()
        self.resources.load(model_id)

    def unload_model(self, model_id: str | None = None) -> None:
        self._require_enabled()
        selected = model_id or self.configuration.default_generation_model
        if selected is None:
            raise AiModelError("No default generation model is configured.")
        self.resources.unload(selected)

    def generate(
        self,
        task: str,
        user_text: str,
        *,
        context: tuple[AiContextItem, ...] = (),
        session_id: UUID | None = None,
        model_id: str | None = None,
        allowed_citations: tuple[str, ...] = (),
    ) -> AiGenerationResult:
        self._require_enabled()
        selected = model_id or self.configuration.default_generation_model
        if selected is None:
            raise AiModelError("No default generation model is configured.")
        contextual = self._bounded_context(session_id, context)
        prompt = self.prompts.build(task, user_text, contextual)
        request = AiGenerationRequest(
            selected,
            task,
            user_text,
            prompt,
            self.configuration.maximum_response_characters,
            contextual,
        )
        result = self.validator.validate_text(
            self.resources.generate(request), allowed_citations=allowed_citations
        )
        if session_id is not None:
            self._remember(session_id, user_text, result.text)
        return result

    def summarize(
        self, text: str, *, session_id: UUID | None = None
    ) -> AiGenerationResult:
        if not text.strip():
            raise AiValidationError("Text to summarize must not be empty.")
        if (
            not self.configuration.enabled
            or not self.configuration.default_generation_model
        ):
            return self.deterministic_summary(text)
        try:
            return self.generate("summarize", text, session_id=session_id)
        except AiError:
            return self.deterministic_summary(text)

    def deterministic_summary(self, text: str) -> AiGenerationResult:
        compact = " ".join(text.split())
        ending = min(
            [
                index
                for index in (
                    compact.find(". "),
                    compact.find("! "),
                    compact.find("? "),
                )
                if index >= 0
            ]
            or [min(len(compact), 500)]
        )
        summary = compact[
            : min(len(compact), ending + (1 if ending < len(compact) else 0), 500)
        ]
        return AiGenerationResult(
            "deterministic",
            None,
            summary,
            False,
            "Local AI is not configured. Omega used a deterministic summary instead.",
        )

    def grounded_answer(
        self,
        question: str,
        sources: tuple[AiContextItem, ...],
        *,
        session_id: UUID | None = None,
    ) -> AiGenerationResult:
        if not self.configuration.enable_grounded_answers:
            raise AiDisabledError("AI-grounded answers are disabled.")
        bounded = sources[: self.configuration.maximum_grounding_chunks]
        allowed = tuple(item.source_id for item in bounded)
        result = self.generate(
            "grounded_answer",
            question,
            context=bounded,
            session_id=session_id,
            allowed_citations=allowed,
        )
        if not result.citations:
            raise AiValidationError("A grounded AI answer must cite provided sources.")
        source_map = {item.source_id: item for item in bounded}
        grounding = tuple(
            AiGroundingSource(
                source_id,
                source_id,
                source_map[source_id].text[:500],
                source_map[source_id].location,
            )
            for source_id in result.citations
        )
        return AiGenerationResult(
            result.request_id,
            result.model_id,
            result.text,
            True,
            _WARNING + " Answered only from the cited local context.",
            result.citations,
            grounding,
            result.usage,
            result.completed_at,
        )

    def embeddings(self, texts: tuple[str, ...]) -> AiEmbeddingResult:
        self._require_enabled()
        model_id = self.configuration.default_embedding_model
        if model_id is None:
            raise AiModelError("No local embedding model is configured.")
        if len(texts) > self.configuration.maximum_grounding_chunks:
            raise AiValidationError("Too many embedding inputs were requested.")
        if (
            sum(len(item) for item in texts)
            > self.configuration.maximum_grounding_characters
        ):
            raise AiValidationError("Embedding input exceeds the configured limit.")
        model = self.models.require(model_id)
        if AiModelCapability.EMBEDDING not in model.capabilities:
            raise AiModelError("The configured model does not support embeddings.")
        return self.resources.embed(AiEmbeddingRequest(model_id, texts))

    def workflow_proposal(
        self, request: str, *, allowed_step_types: tuple[str, ...]
    ) -> dict[str, JsonValue]:
        if not self.configuration.enable_workflow_suggestions:
            raise AiDisabledError("AI workflow suggestions are disabled.")
        result = self.generate("workflow_proposal", request)
        return self.validator.workflow_proposal(
            result.text, allowed_step_types=allowed_step_types
        )

    def cancel(self, request_id: str | None = None) -> int:
        return self.resources.cancel(request_id)

    def clear_context(self, session_id: UUID | None = None) -> None:
        with self._lock:
            if session_id is None:
                self._contexts.clear()
            else:
                self._contexts.pop(session_id, None)

    def context_status(self, session_id: UUID) -> tuple[int, int]:
        with self._lock:
            items = tuple(self._contexts.get(session_id, ()))
        return len(items), sum(len(item.text) for item in items)

    def shutdown(self) -> None:
        self.clear_context()
        self.resources.shutdown()

    def _bounded_context(
        self, session_id: UUID | None, supplied: tuple[AiContextItem, ...]
    ) -> tuple[AiContextItem, ...]:
        with self._lock:
            remembered = tuple(self._contexts.get(session_id, ())) if session_id else ()
        combined = remembered + supplied
        selected: list[AiContextItem] = []
        characters = 0
        for item in reversed(combined):
            if len(selected) >= self.configuration.maximum_context_turns:
                break
            if (
                characters + len(item.text)
                > self.configuration.maximum_context_characters
            ):
                continue
            selected.append(item)
            characters += len(item.text)
        return tuple(reversed(selected))

    def _remember(self, session_id: UUID, user_text: str, response: str) -> None:
        with self._lock:
            items = self._contexts.setdefault(session_id, [])
            items.extend(
                (
                    AiContextItem("conversation-user", AiContextKind.USER, user_text),
                    AiContextItem(
                        "conversation-ai", AiContextKind.TOOL_RESULT, response
                    ),
                )
            )
            if len(items) > self.configuration.maximum_context_turns:
                del items[: len(items) - self.configuration.maximum_context_turns]
            while (
                sum(len(item.text) for item in items)
                > self.configuration.maximum_context_characters
            ):
                del items[0]

    def _require_enabled(self) -> None:
        if not self.configuration.enabled:
            raise AiDisabledError(
                "Local AI is not configured. Deterministic Omega features remain "
                "available."
            )
