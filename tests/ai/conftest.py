from __future__ import annotations

from collections.abc import Iterator

import pytest

from omega.ai import (
    AiConfiguration,
    AiModelCapability,
    AiModelDescriptor,
    AiModelRegistry,
    AiProviderRegistry,
    AiResourceManager,
    AiService,
    FakeAiProvider,
)


def build_ai(
    fake_provider: FakeAiProvider | None = None,
    **overrides: object,
) -> tuple[AiService, FakeAiProvider, AiResourceManager]:
    delay_seconds = float(overrides.pop("delay_seconds", 0))
    load_delay_seconds = float(overrides.pop("load_delay_seconds", 0))
    values: dict[str, object] = {
        "enabled": True,
        "provider": "fake-local",
        "default_generation_model": "fake-generation",
        "default_embedding_model": "fake-embedding",
        "maximum_prompt_characters": 2_000,
        "maximum_response_characters": 1_000,
        "maximum_context_turns": 4,
        "maximum_context_characters": 1_000,
        "maximum_grounding_chunks": 5,
        "maximum_grounding_characters": 2_000,
        "maximum_concurrent_requests": 1,
        "maximum_queued_requests": 1,
        "generation_timeout_seconds": 2,
        "model_load_timeout_seconds": 2,
    }
    values.update(overrides)
    configuration = AiConfiguration.from_mapping(values)
    provider = fake_provider or FakeAiProvider(
        delay_seconds=delay_seconds,
        load_delay_seconds=load_delay_seconds,
    )
    providers = AiProviderRegistry()
    providers.register(provider)
    models = AiModelRegistry(configuration, providers)
    models.register(
        AiModelDescriptor(
            "fake-generation",
            "Fake generation",
            provider.provider_id,
            frozenset({AiModelCapability.GENERATION}),
        )
    )
    models.register(
        AiModelDescriptor(
            "fake-embedding",
            "Fake embeddings",
            provider.provider_id,
            frozenset({AiModelCapability.EMBEDDING}),
            embedding_dimension=4,
            fingerprint="fake-fingerprint",
        )
    )
    resources = AiResourceManager(configuration, providers, models)
    return AiService(configuration, models, resources), provider, resources


@pytest.fixture
def ai_service() -> Iterator[tuple[AiService, FakeAiProvider]]:
    service, provider, _ = build_ai()
    yield service, provider
    service.shutdown()
