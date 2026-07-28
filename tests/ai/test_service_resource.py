from __future__ import annotations

import threading
import time
from dataclasses import replace
from uuid import uuid4

import pytest

from omega.ai import (
    AiContextItem,
    AiContextKind,
    AiDisabledError,
    AiGenerationResult,
    AiModelError,
    AiModelStatus,
    AiRequestCancelledError,
    AiResourceError,
    AiValidationError,
    FakeAiProvider,
)
from omega.ai.cancellation import AiCancellationToken
from omega.ai.models import AiGenerationRequest
from tests.ai.conftest import build_ai


def test_generation_loads_lazily_and_is_labeled(
    ai_service: tuple[object, FakeAiProvider],
) -> None:
    service, provider = ai_service
    result = service.generate("answer", "What is Omega?")  # type: ignore[attr-defined]
    assert result.generated
    assert result.model_id == "fake-generation"
    assert "verify" in result.warning.casefold()
    assert provider.loaded == {"fake-generation"}


def test_duplicate_model_load_is_idempotent(
    ai_service: tuple[object, FakeAiProvider],
) -> None:
    service, provider = ai_service
    service.load_model("fake-generation")  # type: ignore[attr-defined]
    service.load_model("fake-generation")  # type: ignore[attr-defined]
    assert provider.loaded == {"fake-generation"}


def test_model_unload_and_missing_model(
    ai_service: tuple[object, FakeAiProvider],
) -> None:
    service, provider = ai_service
    service.load_model("fake-generation")  # type: ignore[attr-defined]
    service.unload_model("fake-generation")  # type: ignore[attr-defined]
    assert not provider.loaded
    with pytest.raises(AiModelError):
        service.load_model("missing")  # type: ignore[attr-defined]


def test_disabled_generation_and_deterministic_summary() -> None:
    service, _, _ = build_ai(enabled=False, provider=None)
    try:
        with pytest.raises(AiDisabledError):
            service.generate("answer", "question")
        result = service.summarize("First sentence. Second sentence.")
        assert not result.generated
        assert result.model_id is None
        assert result.text == "First sentence."
        assert "deterministic" in result.warning
    finally:
        service.shutdown()


def test_provider_failure_is_contained_and_summary_falls_back() -> None:
    class FailingProvider(FakeAiProvider):
        def generate(
            self,
            request: AiGenerationRequest,
            cancellation: AiCancellationToken,
        ) -> AiGenerationResult:
            del request, cancellation
            raise RuntimeError("private provider failure")

    service, _, _ = build_ai(fake_provider=FailingProvider())
    try:
        result = service.summarize("Safe deterministic fallback sentence.")
        assert not result.generated
        assert result.text == "Safe deterministic fallback sentence."
        assert "private provider failure" not in result.warning
    finally:
        service.shutdown()


def test_embedding_is_local_and_dimension_checked(
    ai_service: tuple[object, FakeAiProvider],
) -> None:
    service, provider = ai_service
    result = service.embeddings(("alpha", "beta"))  # type: ignore[attr-defined]
    assert len(result.vectors) == 2
    assert all(len(vector) == 4 for vector in result.vectors)
    assert len(provider.embedding_requests) == 1


def test_stale_embedding_fingerprint_is_rejected() -> None:
    service, _, _ = build_ai()
    service.models.set_status("fake-embedding", AiModelStatus.AVAILABLE)
    current = service.models.require("fake-embedding")
    service.models._models["fake-embedding"] = replace(current, fingerprint="changed")
    try:
        with pytest.raises(AiResourceError, match="fingerprint"):
            service.embeddings(("alpha",))
    finally:
        service.shutdown()


def test_conversation_is_session_local_bounded_and_clearable(
    ai_service: tuple[object, FakeAiProvider],
) -> None:
    service, _ = ai_service
    one, two = uuid4(), uuid4()
    for index in range(4):
        service.generate("chat", f"turn {index}", session_id=one)  # type: ignore[attr-defined]
    turns, characters = service.context_status(one)  # type: ignore[attr-defined]
    assert turns <= service.configuration.maximum_context_turns  # type: ignore[attr-defined]
    assert characters <= service.configuration.maximum_context_characters  # type: ignore[attr-defined]
    assert service.context_status(two) == (0, 0)  # type: ignore[attr-defined]
    service.clear_context(one)  # type: ignore[attr-defined]
    assert service.context_status(one) == (0, 0)  # type: ignore[attr-defined]


def test_grounded_answer_requires_and_preserves_valid_citations() -> None:
    class CitingProvider(FakeAiProvider):
        def generate(
            self,
            request: AiGenerationRequest,
            cancellation: AiCancellationToken,
        ) -> AiGenerationResult:
            value = super().generate(request, cancellation)
            return replace(value, citations=("doc-1",))

    service, _, resources = build_ai()
    provider = CitingProvider()
    resources.shutdown()
    configuration = service.configuration
    from omega.ai import (
        AiModelCapability,
        AiModelDescriptor,
        AiModelRegistry,
        AiProviderRegistry,
        AiResourceManager,
        AiService,
    )

    providers = AiProviderRegistry()
    providers.register(provider)
    models = AiModelRegistry(configuration, providers)
    models.register(
        AiModelDescriptor(
            "fake-generation",
            "Fake",
            provider.provider_id,
            frozenset({AiModelCapability.GENERATION}),
        )
    )
    resource = AiResourceManager(configuration, providers, models)
    service = AiService(configuration, models, resource)
    try:
        result = service.grounded_answer(
            "What is supported?",
            (AiContextItem("doc-1", AiContextKind.KNOWLEDGE, "Supported fact."),),
        )
        assert result.citations == ("doc-1",)
        assert result.sources[0].excerpt == "Supported fact."
    finally:
        service.shutdown()


def test_grounded_answer_rejects_missing_citation(
    ai_service: tuple[object, FakeAiProvider],
) -> None:
    service, _ = ai_service
    with pytest.raises(AiValidationError, match="must cite"):
        service.grounded_answer(  # type: ignore[attr-defined]
            "question",
            (AiContextItem("doc", AiContextKind.KNOWLEDGE, "fact"),),
        )


def test_generation_can_be_cancelled_cooperatively() -> None:
    service, provider, _ = build_ai(delay_seconds=0.5)
    errors: list[BaseException] = []

    def run() -> None:
        try:
            service.generate("chat", "cancel me")
        except BaseException as error:
            errors.append(error)

    thread = threading.Thread(target=run)
    thread.start()
    deadline = time.monotonic() + 1
    while not provider.generation_requests and time.monotonic() < deadline:
        time.sleep(0.005)
    assert service.cancel() == 1
    thread.join(timeout=2)
    try:
        assert not thread.is_alive()
        assert errors and isinstance(errors[0], AiRequestCancelledError)
    finally:
        service.shutdown()


def test_zero_queue_limit_rejects_duplicate_concurrent_request() -> None:
    service, provider, _ = build_ai(delay_seconds=0.4, maximum_queued_requests=0)
    first_errors: list[BaseException] = []

    def first_request() -> None:
        try:
            service.generate("chat", "first")
        except BaseException as error:
            first_errors.append(error)

    thread = threading.Thread(target=first_request)
    thread.start()
    deadline = time.monotonic() + 1
    while not provider.generation_requests and time.monotonic() < deadline:
        time.sleep(0.005)
    try:
        with pytest.raises(AiResourceError, match="queue is full"):
            service.generate("chat", "second")
    finally:
        service.cancel()
        thread.join(timeout=2)
        service.shutdown()
    assert not first_errors or isinstance(first_errors[0], AiRequestCancelledError)


def test_shutdown_clears_models_and_provider() -> None:
    service, provider, _ = build_ai()
    service.load_model("fake-generation")
    service.shutdown()
    assert provider.shutdown_called
    assert not provider.loaded


def test_generation_timeout_is_bounded() -> None:
    service, _, _ = build_ai(delay_seconds=1.5, generation_timeout_seconds=1)
    try:
        with pytest.raises(AiResourceError, match="timed out"):
            service.generate("chat", "bounded timeout")
    finally:
        service.shutdown()


def test_model_load_timeout_marks_model_failed() -> None:
    service, _, _ = build_ai(load_delay_seconds=1.5, model_load_timeout_seconds=1)
    try:
        with pytest.raises(AiResourceError, match="load timed out"):
            service.load_model("fake-generation")
        assert service.models.require("fake-generation").status is AiModelStatus.FAILED
    finally:
        service.shutdown()
