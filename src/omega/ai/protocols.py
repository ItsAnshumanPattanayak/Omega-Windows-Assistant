"""Provider-independent interfaces for local generation and embeddings."""

from __future__ import annotations

from typing import Protocol

from omega.ai.cancellation import AiCancellationToken
from omega.ai.models import (
    AiEmbeddingRequest,
    AiEmbeddingResult,
    AiGenerationRequest,
    AiGenerationResult,
    AiModelCapability,
    AiModelDescriptor,
)


class AiProvider(Protocol):
    @property
    def provider_id(self) -> str: ...

    @property
    def capabilities(self) -> frozenset[AiModelCapability]: ...

    def validate_model(self, model: AiModelDescriptor) -> bool: ...

    def load_model(
        self, model: AiModelDescriptor, cancellation: AiCancellationToken
    ) -> None: ...

    def unload_model(self, model_id: str) -> None: ...

    def generate(
        self, request: AiGenerationRequest, cancellation: AiCancellationToken
    ) -> AiGenerationResult: ...

    def embed(
        self, request: AiEmbeddingRequest, cancellation: AiCancellationToken
    ) -> AiEmbeddingResult: ...

    def shutdown(self) -> None: ...


LocalTextGenerationProvider = AiProvider
LocalEmbeddingProvider = AiProvider
