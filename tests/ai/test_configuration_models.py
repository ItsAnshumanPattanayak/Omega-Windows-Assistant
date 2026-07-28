from __future__ import annotations

from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path

import pytest

from omega.ai import (
    AiConfiguration,
    AiConfigurationError,
    AiContextItem,
    AiContextKind,
    AiEmbeddingRequest,
    AiEmbeddingResult,
    AiGenerationRequest,
    AiModelCapability,
    AiModelDescriptor,
    AiModelError,
    AiModelRegistry,
    AiModelStatus,
    AiProviderRegistry,
    AiValidationError,
    FakeAiProvider,
    LoopbackHttpAiProvider,
)


def test_configuration_defaults_are_disabled_and_private() -> None:
    value = AiConfiguration.from_mapping({})
    assert not value.enabled
    assert not value.automatically_download_models
    assert not value.allow_remote_endpoints
    assert value.allow_only_loopback_endpoints
    assert not value.enable_ai_command_fallback
    assert not value.enable_conversation_persistence
    assert not value.log_prompts and not value.log_responses


@pytest.mark.parametrize(
    ("values", "message"),
    [
        ({"unknown": True}, "Unknown"),
        ({"enabled": True}, "provider"),
        ({"automatically_download_models": True}, "downloads"),
        ({"allow_remote_endpoints": True}, "Remote"),
        ({"allow_only_loopback_endpoints": False}, "loopback"),
        ({"enable_conversation_persistence": True}, "persistence"),
        ({"log_prompts": True}, "not logged"),
        ({"maximum_prompt_characters": 0}, "between"),
        ({"maximum_concurrent_requests": 5}, "between"),
    ],
)
def test_configuration_rejects_unsafe_values(
    values: dict[str, object], message: str
) -> None:
    with pytest.raises(AiConfigurationError, match=message):
        AiConfiguration.from_mapping(values)


@pytest.mark.parametrize(
    "endpoint",
    ["http://localhost:11434", "http://127.0.0.1:8080", "http://[::1]:9000"],
)
def test_configuration_accepts_loopback_endpoints(endpoint: str) -> None:
    assert AiConfiguration.from_mapping({"endpoint": endpoint}).endpoint == endpoint


@pytest.mark.parametrize(
    "endpoint",
    [
        "https://example.com",
        "http://192.168.1.5:8080",
        "file:///tmp/model",
        "http://user:secret@localhost:8080",
    ],
)
def test_configuration_rejects_non_loopback_or_secret_endpoints(endpoint: str) -> None:
    with pytest.raises(AiConfigurationError):
        AiConfiguration.from_mapping({"endpoint": endpoint})


def test_loopback_provider_rejects_direct_remote_construction() -> None:
    with pytest.raises(AiConfigurationError, match="loopback"):
        LoopbackHttpAiProvider(
            "https://example.com", timeout_seconds=1, maximum_response_bytes=100
        )


def test_model_descriptor_serializes_stable_values() -> None:
    now = datetime.now(UTC)
    model = AiModelDescriptor(
        "model-1",
        "Model One",
        "provider-1",
        frozenset({AiModelCapability.GENERATION}),
        status=AiModelStatus.READY,
        last_validated_at=now,
    )
    assert model.to_dict()["capabilities"] == ["generation"]
    assert model.to_dict()["status"] == "ready"
    assert model.to_dict()["last_validated_at"] == now.isoformat()


@pytest.mark.parametrize("identifier", ["", "UPPER", "bad id", "../escape"])
def test_model_descriptor_rejects_invalid_identifier(identifier: str) -> None:
    with pytest.raises(AiValidationError):
        AiModelDescriptor(
            identifier,
            "Model",
            "provider",
            frozenset({AiModelCapability.GENERATION}),
        )


def test_embedding_model_requires_dimension() -> None:
    with pytest.raises(AiValidationError, match="dimension"):
        AiModelDescriptor(
            "embed",
            "Embed",
            "provider",
            frozenset({AiModelCapability.EMBEDDING}),
        )


def test_external_context_cannot_claim_trust() -> None:
    with pytest.raises(AiValidationError, match="trusted"):
        AiContextItem("mail-1", AiContextKind.EMAIL, "body", trusted=True)


def test_generation_and_embedding_requests_reject_empty_input() -> None:
    with pytest.raises(AiValidationError):
        AiGenerationRequest("model", "task", "", "prompt", 10)
    with pytest.raises(AiValidationError):
        AiEmbeddingRequest("model", ("",))


def test_embedding_result_validates_count_and_dimension() -> None:
    result = AiEmbeddingResult("request", "model", ((0.1, 0.2),), "fingerprint")
    result.validate_dimension(2, 1)
    with pytest.raises(AiValidationError):
        result.validate_dimension(3, 1)
    invalid = AiEmbeddingResult("request", "model", ((float("nan"), 0.2),), "fp")
    with pytest.raises(AiValidationError, match="invalid values"):
        invalid.validate_dimension(2, 1)


def test_explicit_local_model_file_is_fingerprinted(tmp_path: Path) -> None:
    model_path = tmp_path / "model.gguf"
    model_path.write_bytes(b"bounded fake model")
    configuration = AiConfiguration(
        enabled=True,
        provider="fake-local",
        approved_model_directory=tmp_path,
    )
    providers = AiProviderRegistry()
    providers.register(FakeAiProvider())
    registry = AiModelRegistry(configuration, providers)
    model = registry.register(
        AiModelDescriptor(
            "local-model",
            "Local model",
            "fake-local",
            frozenset({AiModelCapability.GENERATION}),
            local_path=str(model_path),
        )
    )
    assert model.fingerprint == sha256(b"bounded fake model").hexdigest()


def test_local_model_path_cannot_escape_approved_directory(tmp_path: Path) -> None:
    outside = tmp_path.parent / "outside-model.gguf"
    outside.write_bytes(b"fake")
    configuration = AiConfiguration(
        enabled=True,
        provider="fake-local",
        approved_model_directory=tmp_path,
    )
    providers = AiProviderRegistry()
    providers.register(FakeAiProvider())
    registry = AiModelRegistry(configuration, providers)
    with pytest.raises(AiModelError, match="leaves"):
        registry.register(
            AiModelDescriptor(
                "outside",
                "Outside",
                "fake-local",
                frozenset({AiModelCapability.GENERATION}),
                local_path=str(outside),
            )
        )
