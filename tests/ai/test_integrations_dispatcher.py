from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest

from omega.ai import (
    AiKnowledgeAssistant,
    AiPermissionError,
    AiProposalService,
    PluginAiAccess,
)
from omega.app import OmegaApplication
from omega.execution.ai_dispatcher import AiDispatcher
from omega.knowledge.models import (
    KnowledgeAnswer,
    KnowledgeSearchQuery,
    KnowledgeSearchResult,
)
from omega.models import CommandSource, IntentType
from omega.safety import SafeExecutionGateway
from omega.understanding.parser import CommandParser
from tests.ai.conftest import build_ai


@pytest.mark.parametrize(
    ("method", "domain"),
    [
        ("email_draft", "email"),
        ("calendar_description", "calendar"),
        ("note_rewrite", "note"),
        ("task_suggestions", "task"),
    ],
)
def test_domain_ai_outputs_are_unapplied_proposals(method: str, domain: str) -> None:
    service, _, _ = build_ai()
    try:
        proposal = getattr(AiProposalService(service), method)("Private source text")
        assert proposal.domain == domain
        assert proposal.generated
        assert not proposal.applied
        assert "verify" in proposal.warning.casefold()
    finally:
        service.shutdown()


def test_workflow_proposal_is_validated_but_never_saved_or_executed() -> None:
    service, _, _ = build_ai()
    try:
        proposal = service.workflow_proposal(
            "Show a reviewed message", allowed_step_types=("display_message",)
        )
        assert proposal["steps"] == [{"type": "display_message", "arguments": {}}]
    finally:
        service.shutdown()


def test_knowledge_assistant_preserves_deterministic_fallback() -> None:
    class Knowledge:
        def search(self, query: KnowledgeSearchQuery) -> KnowledgeSearchResult:
            return KnowledgeSearchResult(query, ())

        def answer(self, question: str) -> KnowledgeAnswer:
            return KnowledgeAnswer(question, "Extractive cited fallback.", (), False)

    service, _, _ = build_ai(enabled=False, provider=None)
    try:
        result = AiKnowledgeAssistant(service, Knowledge()).answer("question")
        assert not result.generated
        assert result.text == "Extractive cited fallback."
        assert "extractive" in result.warning
    finally:
        service.shutdown()


def test_plugin_permission_revocation_and_quota() -> None:
    service, provider, _ = build_ai()
    approved: set[str] = set()

    def check(plugin_id: str, version: str, fingerprint: str, permission: str) -> None:
        del plugin_id, version, fingerprint
        if permission not in approved:
            raise PermissionError("revoked")

    access = PluginAiAccess(service, check, maximum_requests_per_session=1)
    session_id = uuid4()
    try:
        with pytest.raises(AiPermissionError):
            access.generate("plugin", "1.0.0", "fingerprint", session_id, "data")
        approved.add("use_local_ai_generation")
        result = access.generate(
            "plugin",
            "1.0.0",
            "fingerprint",
            session_id,
            "untrusted plugin data",
        )
        assert result.generated
        prompt = provider.generation_requests[-1].prompt
        assert 'type="plugin"' in prompt
        with pytest.raises(AiPermissionError, match="quota"):
            access.generate(
                "plugin",
                "1.0.0",
                "fingerprint",
                session_id,
                "again",
            )
        access.clear_session(session_id)
        approved.clear()
        approved.add("use_local_ai_embeddings")
        embedded = access.embeddings(
            "plugin", "1.0.0", "fingerprint", session_id, ("bounded",)
        )
        assert len(embedded.vectors[0]) == 4
    finally:
        service.shutdown()


@pytest.mark.parametrize(
    ("text", "intent", "entity"),
    [
        ("Show local AI status", IntentType.SHOW_LOCAL_AI_STATUS, None),
        ("List local AI models", IntentType.LIST_LOCAL_AI_MODELS, None),
        ("Load model tiny", IntentType.LOAD_LOCAL_AI_MODEL, "tiny"),
        ("Ask local AI explain Omega", IntentType.ASK_LOCAL_AI, "explain Omega"),
        (
            "Summarize text: one two three",
            IntentType.SUMMARIZE_TEXT_WITH_AI,
            "one two three",
        ),
        ("Cancel AI generation", IntentType.CANCEL_AI_GENERATION, None),
        ("Clear AI conversation", IntentType.CLEAR_AI_CONVERSATION, None),
    ],
)
def test_parser_ai_intents_and_entities(
    text: str, intent: IntentType, entity: str | None
) -> None:
    result = CommandParser().parse(text)
    assert result.command.intent is intent
    assert result.matched and not result.requires_clarification
    if entity is not None:
        assert result.command.entities[0].value == entity


def test_dispatcher_generation_uses_redacted_persistence_receipt() -> None:
    service, provider, _ = build_ai()
    dispatcher = AiDispatcher(service, SafeExecutionGateway())
    parsed = CommandParser().parse("Ask local AI my private question", uuid4())
    try:
        dispatched = dispatcher.dispatch(parsed)
        assert dispatched is not None
        assert "Local AI" in dispatched.user_message
        assert "private question" in provider.generation_requests[0].user_text
        assert dispatched.command.original_text == "[ask_local_ai]"
        assert "private question" not in dispatched.result.user_message
        assert dispatched.result.metadata["generated_content_omitted"] is True
    finally:
        service.shutdown()


def test_voice_cannot_load_model_path_or_identifier() -> None:
    service, provider, _ = build_ai()
    dispatcher = AiDispatcher(service, SafeExecutionGateway())
    parsed = CommandParser().parse(
        "Load model fake-generation", uuid4(), source=CommandSource.VOICE
    )
    try:
        dispatched = dispatcher.dispatch(parsed)
        assert dispatched is not None
        assert "typed input" in dispatched.user_message
        assert not provider.loaded
    finally:
        service.shutdown()


def test_generated_text_is_not_dispatched_as_a_command() -> None:
    service, provider, _ = build_ai()
    provider._factory = lambda request: "delete file important.txt"
    dispatcher = AiDispatcher(service, SafeExecutionGateway())
    parsed = CommandParser().parse("Ask local AI suggest something", uuid4())
    try:
        dispatched = dispatcher.dispatch(parsed)
        assert dispatched is not None
        assert "delete file important.txt" in dispatched.user_message
        assert dispatched.action.intent is IntentType.ASK_LOCAL_AI
        assert len(provider.generation_requests) == 1
    finally:
        service.shutdown()


def test_application_composes_disabled_ai_without_breaking_session(
    tmp_path: Path,
) -> None:
    application = OmegaApplication(database_path=tmp_path / "omega.db")
    try:
        application.session.handle_input("Hello Omega")
        response = application.session.handle_input("Show local AI status")
        assert "disabled" in response
        assert "deterministic" in response
    finally:
        application.shutdown()
