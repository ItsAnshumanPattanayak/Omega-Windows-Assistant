"""Bounded model lifecycle, queueing, timeout, and cancellation management."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeoutError
from threading import BoundedSemaphore, RLock

from omega.ai.cancellation import AiCancellationToken
from omega.ai.configuration import AiConfiguration
from omega.ai.exceptions import AiError, AiProviderError, AiResourceError
from omega.ai.models import (
    AiEmbeddingRequest,
    AiEmbeddingResult,
    AiGenerationRequest,
    AiGenerationResult,
    AiModelCapability,
    AiModelStatus,
    AiProviderStatus,
)
from omega.ai.registry import AiModelRegistry, AiProviderRegistry


class AiResourceManager:
    """Own optional provider work explicitly; nothing starts at import time."""

    def __init__(
        self,
        configuration: AiConfiguration,
        providers: AiProviderRegistry,
        models: AiModelRegistry,
    ) -> None:
        self.configuration = configuration
        self.providers = providers
        self.models = models
        self._slots = BoundedSemaphore(configuration.maximum_concurrent_requests)
        self._executor = ThreadPoolExecutor(
            max_workers=configuration.maximum_concurrent_requests,
            thread_name_prefix="omega-local-ai",
        )
        self._lock = RLock()
        self._loaded: set[str] = set()
        self._loading: set[str] = set()
        self._tokens: dict[str, AiCancellationToken] = {}
        self._active = 0
        self._queued = 0
        self._closed = False

    def load(self, model_id: str) -> None:
        model = self.models.require(model_id)
        with self._lock:
            self._ensure_open()
            if model_id in self._loaded:
                return
            if model_id in self._loading:
                raise AiResourceError("The local AI model is already loading.")
            self._loading.add(model_id)
        token = AiCancellationToken()
        self.models.set_status(model_id, AiModelStatus.LOADING)
        provider = self.providers.require(model.provider_id)
        future = self._executor.submit(provider.load_model, model, token)
        try:
            future.result(timeout=self.configuration.model_load_timeout_seconds)
        except FutureTimeoutError as error:
            token.cancel()
            self.models.set_status(model_id, AiModelStatus.FAILED)
            raise AiResourceError("The local AI model load timed out.") from error
        except Exception as error:
            self.models.set_status(model_id, AiModelStatus.FAILED)
            if isinstance(error, AiError):
                raise
            raise AiProviderError("The local AI model failed to load.") from error
        finally:
            with self._lock:
                self._loading.discard(model_id)
        with self._lock:
            self._loaded.add(model_id)
        self.models.set_status(model_id, AiModelStatus.READY)

    def unload(self, model_id: str) -> None:
        model = self.models.require(model_id)
        with self._lock:
            if model_id not in self._loaded:
                self.models.set_status(model_id, AiModelStatus.UNLOADED)
                return
            if any(request.startswith(model_id + ":") for request in self._tokens):
                raise AiResourceError("The local AI model is busy.")
        self.providers.require(model.provider_id).unload_model(model_id)
        with self._lock:
            self._loaded.discard(model_id)
        self.models.set_status(model_id, AiModelStatus.UNLOADED)

    def generate(self, request: AiGenerationRequest) -> AiGenerationResult:
        model = self.models.require(request.model_id)
        if AiModelCapability.GENERATION not in model.capabilities:
            raise AiResourceError("The selected model does not support generation.")
        self.load(model.model_id)
        token = self._enter(model.model_id, request.request_id)
        provider = self.providers.require(model.provider_id)
        future = self._executor.submit(provider.generate, request, token)
        try:
            return future.result(timeout=self.configuration.generation_timeout_seconds)
        except FutureTimeoutError as error:
            token.cancel()
            raise AiResourceError("Local AI generation timed out.") from error
        except Exception as error:
            if isinstance(error, AiError):
                raise
            raise AiProviderError("The local AI provider failed safely.") from error
        finally:
            self._leave(model.model_id, request.request_id)

    def embed(self, request: AiEmbeddingRequest) -> AiEmbeddingResult:
        model = self.models.require(request.model_id)
        if AiModelCapability.EMBEDDING not in model.capabilities:
            raise AiResourceError("The selected model does not support embeddings.")
        self.load(model.model_id)
        token = self._enter(model.model_id, request.request_id)
        provider = self.providers.require(model.provider_id)
        future = self._executor.submit(provider.embed, request, token)
        try:
            result = future.result(
                timeout=self.configuration.generation_timeout_seconds
            )
            if model.embedding_dimension is None:
                raise AiResourceError("The embedding model dimension is unavailable.")
            result.validate_dimension(model.embedding_dimension, len(request.texts))
            if model.fingerprint and result.model_fingerprint != model.fingerprint:
                raise AiResourceError("The embedding model fingerprint is stale.")
            return result
        except FutureTimeoutError as error:
            token.cancel()
            raise AiResourceError("Local embedding generation timed out.") from error
        except Exception as error:
            if isinstance(error, AiError):
                raise
            raise AiProviderError(
                "The local embedding provider failed safely."
            ) from error
        finally:
            self._leave(model.model_id, request.request_id)

    def cancel(self, request_id: str | None = None) -> int:
        with self._lock:
            selected = [
                token
                for key, token in self._tokens.items()
                if request_id is None or key.endswith(":" + request_id)
            ]
        for token in selected:
            token.cancel()
        return len(selected)

    def status(self, provider_id: str | None) -> AiProviderStatus:
        with self._lock:
            loaded = tuple(sorted(self._loaded))
            active, queued = self._active, self._queued
        return AiProviderStatus(
            self.configuration.enabled,
            provider_id,
            loaded,
            active,
            queued,
            "Local AI is ready." if loaded else "No local AI model is loaded.",
        )

    def shutdown(self) -> None:
        with self._lock:
            if self._closed:
                return
            self._closed = True
            tokens = tuple(self._tokens.values())
            loaded = tuple(self._loaded)
        for token in tokens:
            token.cancel()
        for model_id in loaded:
            try:
                model = self.models.require(model_id)
                self.providers.require(model.provider_id).unload_model(model_id)
            except Exception:
                continue
        self.providers.shutdown()
        self._executor.shutdown(wait=False, cancel_futures=True)

    def _enter(self, model_id: str, request_id: str) -> AiCancellationToken:
        with self._lock:
            self._ensure_open()
            if self._active >= self.configuration.maximum_concurrent_requests:
                if self._queued >= self.configuration.maximum_queued_requests:
                    raise AiResourceError("The local AI request queue is full.")
                self._queued += 1
                queued = True
            else:
                queued = False
        acquired = self._slots.acquire(
            timeout=self.configuration.generation_timeout_seconds
        )
        with self._lock:
            if queued:
                self._queued -= 1
            if not acquired:
                raise AiResourceError("The local AI request queue timed out.")
            token = AiCancellationToken()
            self._tokens[f"{model_id}:{request_id}"] = token
            self._active += 1
            self.models.set_status(model_id, AiModelStatus.BUSY)
            return token

    def _leave(self, model_id: str, request_id: str) -> None:
        with self._lock:
            token = self._tokens.pop(f"{model_id}:{request_id}", None)
            if token is None:
                return
            self._active -= 1
            self.models.set_status(model_id, AiModelStatus.READY)
        self._slots.release()

    def _ensure_open(self) -> None:
        if self._closed:
            raise AiResourceError("The local AI resource manager is shut down.")
