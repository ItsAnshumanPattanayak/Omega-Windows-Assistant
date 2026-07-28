"""Immutable serializable records for controlled local-AI requests."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from math import isfinite
from typing import Any

from omega.ai.exceptions import AiValidationError
from omega.models._serialization import (
    JsonValue,
    serialize_value,
    utc_now,
    validate_utc_timestamp,
)

_IDENTIFIER = re.compile(r"^[a-z0-9][a-z0-9._/-]{0,127}$")


class AiModelCapability(StrEnum):
    GENERATION = "generation"
    EMBEDDING = "embedding"


class AiModelStatus(StrEnum):
    CONFIGURED = "configured"
    AVAILABLE = "available"
    MISSING = "missing"
    INVALID = "invalid"
    INCOMPATIBLE = "incompatible"
    LOADING = "loading"
    READY = "ready"
    BUSY = "busy"
    FAILED = "failed"
    UNLOADED = "unloaded"


class AiContextKind(StrEnum):
    USER = "user"
    KNOWLEDGE = "knowledge"
    EMAIL = "email"
    CALENDAR = "calendar"
    NOTE = "note"
    WORKFLOW = "workflow"
    PLUGIN = "plugin"
    TOOL_RESULT = "tool_result"
    DOCUMENT = "document"
    CLIPBOARD = "clipboard"


@dataclass(frozen=True)
class AiModelDescriptor:
    model_id: str
    display_name: str
    provider_id: str
    capabilities: frozenset[AiModelCapability]
    provider_model_name: str | None = None
    local_path: str | None = None
    context_window_limit: int = 4096
    maximum_output_length: int = 1024
    embedding_dimension: int | None = None
    quantization: str | None = None
    estimated_memory_bytes: int | None = None
    status: AiModelStatus = AiModelStatus.CONFIGURED
    fingerprint: str | None = None
    last_validated_at: datetime | None = None

    def __post_init__(self) -> None:
        for value, label in ((self.model_id, "model"), (self.provider_id, "provider")):
            if not _IDENTIFIER.fullmatch(value):
                raise AiValidationError(f"The {label} identifier is invalid.")
        if not self.display_name.strip() or len(self.display_name) > 200:
            raise AiValidationError("The model display name is invalid.")
        if not self.capabilities:
            raise AiValidationError("A model must declare at least one capability.")
        if self.context_window_limit <= 0 or self.maximum_output_length <= 0:
            raise AiValidationError("Model size limits must be positive.")
        if self.embedding_dimension is not None and self.embedding_dimension <= 0:
            raise AiValidationError("Embedding dimension must be positive.")
        if (
            AiModelCapability.EMBEDDING in self.capabilities
            and self.embedding_dimension is None
        ):
            raise AiValidationError("Embedding models require a declared dimension.")
        if self.last_validated_at is not None:
            object.__setattr__(
                self,
                "last_validated_at",
                validate_utc_timestamp(self.last_validated_at, "last_validated_at"),
            )

    def to_dict(self) -> dict[str, JsonValue]:
        capabilities: list[JsonValue] = [
            item.value for item in sorted(self.capabilities)
        ]
        return {
            "model_id": self.model_id,
            "display_name": self.display_name,
            "provider_id": self.provider_id,
            "capabilities": capabilities,
            "provider_model_name": self.provider_model_name,
            "local_path": self.local_path,
            "context_window_limit": self.context_window_limit,
            "maximum_output_length": self.maximum_output_length,
            "embedding_dimension": self.embedding_dimension,
            "quantization": self.quantization,
            "estimated_memory_bytes": self.estimated_memory_bytes,
            "status": self.status.value,
            "fingerprint": self.fingerprint,
            "last_validated_at": serialize_value(self.last_validated_at),
        }


@dataclass(frozen=True)
class AiContextItem:
    source_id: str
    kind: AiContextKind
    text: str
    trusted: bool = False
    location: str | None = None

    def __post_init__(self) -> None:
        if not self.source_id.strip() or len(self.source_id) > 300:
            raise AiValidationError("AI context source identifiers are required.")
        if not self.text.strip():
            raise AiValidationError("AI context text must not be empty.")
        if self.kind is not AiContextKind.USER and self.trusted:
            raise AiValidationError("External AI context cannot be marked trusted.")


@dataclass(frozen=True)
class AiGroundingSource:
    source_id: str
    label: str
    excerpt: str
    location: str | None = None


@dataclass(frozen=True)
class AiGenerationRequest:
    model_id: str
    task: str
    user_text: str
    prompt: str
    maximum_output_characters: int
    context: tuple[AiContextItem, ...] = ()
    request_id: str = field(default_factory=lambda: __import__("uuid").uuid4().hex)

    def __post_init__(self) -> None:
        if not _IDENTIFIER.fullmatch(self.model_id):
            raise AiValidationError("The generation model identifier is invalid.")
        if (
            not self.task.strip()
            or not self.user_text.strip()
            or not self.prompt.strip()
        ):
            raise AiValidationError("Generation request text must not be empty.")
        if self.maximum_output_characters <= 0:
            raise AiValidationError("The generation output limit must be positive.")


@dataclass(frozen=True)
class AiUsageMetrics:
    prompt_characters: int
    response_characters: int
    duration_ms: int

    def __post_init__(self) -> None:
        if min(self.prompt_characters, self.response_characters, self.duration_ms) < 0:
            raise AiValidationError("AI usage metrics must be non-negative.")


@dataclass(frozen=True)
class AiGenerationResult:
    request_id: str
    model_id: str | None
    text: str
    generated: bool
    warning: str
    citations: tuple[str, ...] = ()
    sources: tuple[AiGroundingSource, ...] = ()
    usage: AiUsageMetrics | None = None
    completed_at: datetime = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        if (
            not self.request_id.strip()
            or not self.text.strip()
            or not self.warning.strip()
        ):
            raise AiValidationError("The AI generation result is incomplete.")
        object.__setattr__(
            self,
            "completed_at",
            validate_utc_timestamp(self.completed_at, "completed_at"),
        )

    def to_dict(self) -> dict[str, JsonValue]:
        return {
            "request_id": self.request_id,
            "model_id": self.model_id,
            "text": self.text,
            "generated": self.generated,
            "warning": self.warning,
            "citations": list(self.citations),
            "sources": [
                {
                    "source_id": item.source_id,
                    "label": item.label,
                    "excerpt": item.excerpt,
                    "location": item.location,
                }
                for item in self.sources
            ],
            "usage": (
                None
                if self.usage is None
                else {
                    "prompt_characters": self.usage.prompt_characters,
                    "response_characters": self.usage.response_characters,
                    "duration_ms": self.usage.duration_ms,
                }
            ),
            "completed_at": serialize_value(self.completed_at),
        }


@dataclass(frozen=True)
class AiEmbeddingRequest:
    model_id: str
    texts: tuple[str, ...]
    request_id: str = field(default_factory=lambda: __import__("uuid").uuid4().hex)

    def __post_init__(self) -> None:
        if not _IDENTIFIER.fullmatch(self.model_id) or not self.texts:
            raise AiValidationError("The embedding request is invalid.")
        if any(not item.strip() for item in self.texts):
            raise AiValidationError("Embedding input must not be empty.")


@dataclass(frozen=True)
class AiEmbeddingResult:
    request_id: str
    model_id: str
    vectors: tuple[tuple[float, ...], ...]
    model_fingerprint: str

    def validate_dimension(self, expected: int, input_count: int) -> None:
        if len(self.vectors) != input_count or any(
            len(vector) != expected for vector in self.vectors
        ):
            raise AiValidationError("The embedding response dimension is invalid.")
        if any(not isfinite(value) for vector in self.vectors for value in vector):
            raise AiValidationError("The embedding response contains invalid values.")


@dataclass(frozen=True)
class AiProviderStatus:
    enabled: bool
    provider_id: str | None
    loaded_models: tuple[str, ...]
    active_requests: int
    queued_requests: int
    message: str


def json_object(value: Any) -> dict[str, JsonValue]:
    """Narrow a decoded JSON object without accepting executable objects."""

    if not isinstance(value, dict) or any(not isinstance(key, str) for key in value):
        raise AiValidationError("Structured AI output must be a JSON object.")
    return value
