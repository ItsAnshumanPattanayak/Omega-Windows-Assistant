"""Safe fake provider and optional loopback HTTP adapter."""

from __future__ import annotations

import json
import time
from collections.abc import Callable
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from omega.ai.cancellation import AiCancellationToken
from omega.ai.configuration import AiConfiguration
from omega.ai.exceptions import AiProviderError
from omega.ai.models import (
    AiEmbeddingRequest,
    AiEmbeddingResult,
    AiGenerationRequest,
    AiGenerationResult,
    AiModelCapability,
    AiModelDescriptor,
    AiUsageMetrics,
)


class FakeAiProvider:
    """Deterministic side-effect-free provider used by standard tests."""

    def __init__(
        self,
        *,
        provider_id: str = "fake-local",
        response_factory: Callable[[AiGenerationRequest], str] | None = None,
        delay_seconds: float = 0.0,
        load_delay_seconds: float = 0.0,
    ) -> None:
        self._provider_id = provider_id
        self._factory = response_factory or self._default_response
        self.delay_seconds = delay_seconds
        self.load_delay_seconds = load_delay_seconds
        self.loaded: set[str] = set()
        self.generation_requests: list[AiGenerationRequest] = []
        self.embedding_requests: list[AiEmbeddingRequest] = []
        self.shutdown_called = False

    @property
    def provider_id(self) -> str:
        return self._provider_id

    @property
    def capabilities(self) -> frozenset[AiModelCapability]:
        return frozenset(AiModelCapability)

    def validate_model(self, model: AiModelDescriptor) -> bool:
        return model.provider_id == self.provider_id

    def load_model(
        self, model: AiModelDescriptor, cancellation: AiCancellationToken
    ) -> None:
        deadline = time.monotonic() + self.load_delay_seconds
        while time.monotonic() < deadline:
            cancellation.raise_if_cancelled()
            time.sleep(min(0.005, max(0.0, deadline - time.monotonic())))
        cancellation.raise_if_cancelled()
        self.loaded.add(model.model_id)

    def unload_model(self, model_id: str) -> None:
        self.loaded.discard(model_id)

    def generate(
        self, request: AiGenerationRequest, cancellation: AiCancellationToken
    ) -> AiGenerationResult:
        started = time.monotonic()
        self.generation_requests.append(request)
        deadline = started + self.delay_seconds
        while time.monotonic() < deadline:
            cancellation.raise_if_cancelled()
            time.sleep(min(0.005, max(0.0, deadline - time.monotonic())))
        cancellation.raise_if_cancelled()
        text = self._factory(request)
        return AiGenerationResult(
            request.request_id,
            request.model_id,
            text,
            True,
            "Generated locally; verify this output before using it.",
            usage=AiUsageMetrics(
                len(request.prompt), len(text), int((time.monotonic() - started) * 1000)
            ),
        )

    def embed(
        self, request: AiEmbeddingRequest, cancellation: AiCancellationToken
    ) -> AiEmbeddingResult:
        self.embedding_requests.append(request)
        vectors = []
        for text in request.texts:
            cancellation.raise_if_cancelled()
            seed = sum(ord(character) for character in text)
            vectors.append(tuple(((seed + index) % 101) / 100 for index in range(4)))
        return AiEmbeddingResult(
            request.request_id, request.model_id, tuple(vectors), "fake-fingerprint"
        )

    def shutdown(self) -> None:
        self.loaded.clear()
        self.shutdown_called = True

    @staticmethod
    def _default_response(request: AiGenerationRequest) -> str:
        if request.task == "workflow_proposal":
            return json.dumps(
                {
                    "name": "Suggested workflow",
                    "description": "Review before saving.",
                    "steps": [{"type": "display_message", "arguments": {}}],
                }
            )
        if request.task == "command_proposal":
            return json.dumps(
                {
                    "intent": "unknown",
                    "entities": [],
                    "confidence": 0.0,
                    "explanation": "No deterministic match.",
                    "clarify": True,
                }
            )
        return f"Local AI draft: {request.user_text.strip()}"


class LoopbackHttpAiProvider:
    """Optional adapter for a separately trusted loopback JSON runtime."""

    def __init__(
        self,
        endpoint: str,
        *,
        timeout_seconds: int,
        maximum_response_bytes: int,
    ) -> None:
        AiConfiguration._validate_endpoint(endpoint)
        if timeout_seconds <= 0 or maximum_response_bytes <= 0:
            raise AiProviderError("Loopback provider limits must be positive.")
        self.endpoint = endpoint.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.maximum_response_bytes = maximum_response_bytes

    @property
    def provider_id(self) -> str:
        return "loopback-http"

    @property
    def capabilities(self) -> frozenset[AiModelCapability]:
        return frozenset(AiModelCapability)

    def validate_model(self, model: AiModelDescriptor) -> bool:
        return model.provider_id == self.provider_id and bool(
            model.provider_model_name or model.model_id
        )

    def load_model(
        self, model: AiModelDescriptor, cancellation: AiCancellationToken
    ) -> None:
        cancellation.raise_if_cancelled()
        self._post("/load", {"model": model.provider_model_name or model.model_id})

    def unload_model(self, model_id: str) -> None:
        self._post("/unload", {"model": model_id})

    def generate(
        self, request: AiGenerationRequest, cancellation: AiCancellationToken
    ) -> AiGenerationResult:
        cancellation.raise_if_cancelled()
        payload = self._post(
            "/generate",
            {
                "model": request.model_id,
                "prompt": request.prompt,
                "maximum_output_characters": request.maximum_output_characters,
            },
        )
        cancellation.raise_if_cancelled()
        text = payload.get("text")
        if not isinstance(text, str):
            raise AiProviderError("The loopback provider response is malformed.")
        citations_value = payload.get("citations", [])
        if not isinstance(citations_value, list) or any(
            not isinstance(item, str) for item in citations_value
        ):
            raise AiProviderError("The loopback provider citations are malformed.")
        return AiGenerationResult(
            request.request_id,
            request.model_id,
            text,
            True,
            "Generated by a separately trusted local runtime; verify this output.",
            citations=tuple(citations_value),
        )

    def embed(
        self, request: AiEmbeddingRequest, cancellation: AiCancellationToken
    ) -> AiEmbeddingResult:
        cancellation.raise_if_cancelled()
        payload = self._post(
            "/embed", {"model": request.model_id, "texts": list(request.texts)}
        )
        vectors_value = payload.get("vectors")
        fingerprint = payload.get("model_fingerprint")
        if not isinstance(vectors_value, list) or not isinstance(fingerprint, str):
            raise AiProviderError("The loopback embedding response is malformed.")
        vectors: list[tuple[float, ...]] = []
        for vector in vectors_value:
            if not isinstance(vector, list) or any(
                isinstance(item, bool) or not isinstance(item, (int, float))
                for item in vector
            ):
                raise AiProviderError("The loopback embedding vector is malformed.")
            vectors.append(tuple(float(item) for item in vector))
        return AiEmbeddingResult(
            request.request_id,
            request.model_id,
            tuple(vectors),
            fingerprint,
        )

    def shutdown(self) -> None:
        return None

    def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        request = Request(
            self.endpoint + path,
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                raw = response.read(self.maximum_response_bytes + 1)
        except (HTTPError, URLError, OSError, TimeoutError) as error:
            raise AiProviderError(
                "The configured local AI runtime is unavailable."
            ) from error
        if len(raw) > self.maximum_response_bytes:
            raise AiProviderError("The local AI runtime response is too large.")
        try:
            value = json.loads(raw.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeError) as error:
            raise AiProviderError(
                "The local AI runtime returned invalid JSON."
            ) from error
        if not isinstance(value, dict) or any(
            not isinstance(key, str) for key in value
        ):
            raise AiProviderError("The local AI runtime response is malformed.")
        return value
