"""Explicit provider and model registries with no filesystem-wide discovery."""

from __future__ import annotations

from dataclasses import replace
from hashlib import sha256
from pathlib import Path
from threading import RLock

from omega.ai.configuration import AiConfiguration
from omega.ai.exceptions import AiModelError, AiProviderError
from omega.ai.models import AiModelDescriptor, AiModelStatus
from omega.ai.protocols import AiProvider
from omega.models._serialization import utc_now


class AiProviderRegistry:
    def __init__(self) -> None:
        self._providers: dict[str, AiProvider] = {}

    def register(self, provider: AiProvider) -> None:
        if provider.provider_id in self._providers:
            raise AiProviderError("The AI provider is already registered.")
        self._providers[provider.provider_id] = provider

    def require(self, provider_id: str) -> AiProvider:
        provider = self._providers.get(provider_id)
        if provider is None:
            raise AiProviderError("The configured local AI provider is unavailable.")
        return provider

    def shutdown(self) -> None:
        for provider in tuple(self._providers.values()):
            provider.shutdown()


class AiModelRegistry:
    def __init__(
        self,
        configuration: AiConfiguration,
        providers: AiProviderRegistry,
    ) -> None:
        self.configuration = configuration
        self.providers = providers
        self._models: dict[str, AiModelDescriptor] = {}
        self._lock = RLock()

    def register(self, model: AiModelDescriptor) -> AiModelDescriptor:
        provider = self.providers.require(model.provider_id)
        self._validate_local_path(model.local_path)
        if not model.capabilities.issubset(provider.capabilities):
            raise AiModelError("The provider does not support every model capability.")
        if not provider.validate_model(model):
            raise AiModelError("The provider rejected the model descriptor.")
        fingerprint = model.fingerprint
        if model.local_path is not None and fingerprint is None:
            fingerprint = self.fingerprint_file(Path(model.local_path))
        validated = replace(
            model,
            status=AiModelStatus.AVAILABLE,
            fingerprint=fingerprint,
            last_validated_at=utc_now(),
        )
        with self._lock:
            if model.model_id in self._models:
                raise AiModelError("The AI model is already registered.")
            self._models[model.model_id] = validated
        return validated

    def require(self, model_id: str) -> AiModelDescriptor:
        with self._lock:
            model = self._models.get(model_id)
        if model is None:
            raise AiModelError("The requested local AI model was not found.")
        return model

    def list(self) -> tuple[AiModelDescriptor, ...]:
        with self._lock:
            return tuple(sorted(self._models.values(), key=lambda item: item.model_id))

    def set_status(self, model_id: str, status: AiModelStatus) -> AiModelDescriptor:
        with self._lock:
            current = self.require(model_id)
            updated = replace(current, status=status)
            self._models[model_id] = updated
            return updated

    def _validate_local_path(self, raw_path: str | None) -> None:
        if raw_path is None:
            return
        approved = self.configuration.approved_model_directory
        if approved is None:
            raise AiModelError("A local model path requires an approved directory.")
        root = approved.resolve(strict=False)
        path = Path(raw_path)
        resolved = path.resolve(strict=False)
        try:
            resolved.relative_to(root)
        except ValueError as error:
            raise AiModelError(
                "The model path leaves the approved directory."
            ) from error
        if path.is_symlink() or any(parent.is_symlink() for parent in path.parents):
            raise AiModelError("Symlinked model paths are not allowed.")
        if not path.is_file():
            raise AiModelError("The configured local model file is missing.")

    @staticmethod
    def fingerprint_file(path: Path) -> str:
        """Hash one explicitly configured file without scanning its directory."""

        digest = sha256()
        try:
            with path.open("rb") as model_file:
                while chunk := model_file.read(1_048_576):
                    digest.update(chunk)
        except OSError as error:
            raise AiModelError(
                "The configured model file could not be validated."
            ) from error
        return digest.hexdigest()
