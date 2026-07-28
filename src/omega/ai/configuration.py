"""Conservative, dependency-free configuration for optional local AI."""

from __future__ import annotations

import ipaddress
from collections.abc import Mapping
from dataclasses import dataclass, fields
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from omega.ai.exceptions import AiConfigurationError


@dataclass(frozen=True)
class AiConfiguration:
    """Validated limits; AI is disabled and local-only by default."""

    enabled: bool = False
    provider: str | None = None
    default_generation_model: str | None = None
    default_embedding_model: str | None = None
    approved_model_directory: Path | None = None
    automatically_download_models: bool = False
    allow_remote_endpoints: bool = False
    allow_only_loopback_endpoints: bool = True
    endpoint: str | None = None
    maximum_prompt_characters: int = 50_000
    maximum_response_characters: int = 10_000
    maximum_context_turns: int = 10
    maximum_context_characters: int = 30_000
    maximum_grounding_chunks: int = 10
    maximum_grounding_characters: int = 30_000
    maximum_concurrent_requests: int = 1
    maximum_queued_requests: int = 5
    generation_timeout_seconds: int = 120
    model_load_timeout_seconds: int = 180
    idle_unload_seconds: int = 600
    unload_model_when_idle: bool = True
    enable_grounded_answers: bool = True
    enable_email_assistance: bool = True
    enable_calendar_assistance: bool = True
    enable_note_assistance: bool = True
    enable_workflow_suggestions: bool = True
    enable_ai_command_fallback: bool = False
    enable_conversation_persistence: bool = False
    require_confirmation_before_applying_generated_changes: bool = True
    expose_model_debug_output: bool = False
    log_prompts: bool = False
    log_responses: bool = False

    def __post_init__(self) -> None:
        self.validate()

    @classmethod
    def from_mapping(cls, values: Mapping[str, Any]) -> AiConfiguration:
        known = {item.name for item in fields(cls)}
        unknown = set(values) - known
        if unknown:
            raise AiConfigurationError(
                "Unknown local_ai setting(s): " + ", ".join(sorted(unknown))
            )
        data = dict(values)
        directory = data.get("approved_model_directory")
        if directory is not None:
            if not isinstance(directory, (str, Path)):
                raise AiConfigurationError(
                    "local_ai.approved_model_directory must be a path."
                )
            data["approved_model_directory"] = Path(directory)
        return cls(**data)

    def validate(self) -> None:
        boolean_names = {
            item.name
            for item in fields(self)
            if item.type is bool or item.type == "bool"
        }
        if any(not isinstance(getattr(self, name), bool) for name in boolean_names):
            raise AiConfigurationError("Local-AI switches must be boolean.")
        integer_bounds = {
            "maximum_prompt_characters": (1, 200_000),
            "maximum_response_characters": (1, 50_000),
            "maximum_context_turns": (1, 50),
            "maximum_context_characters": (1, 100_000),
            "maximum_grounding_chunks": (1, 100),
            "maximum_grounding_characters": (1, 100_000),
            "maximum_concurrent_requests": (1, 4),
            "maximum_queued_requests": (0, 50),
            "generation_timeout_seconds": (1, 600),
            "model_load_timeout_seconds": (1, 900),
            "idle_unload_seconds": (1, 86_400),
        }
        for name, (minimum, maximum) in integer_bounds.items():
            value = getattr(self, name)
            if (
                isinstance(value, bool)
                or not isinstance(value, int)
                or not minimum <= value <= maximum
            ):
                raise AiConfigurationError(
                    f"local_ai.{name} must be between {minimum} and {maximum}."
                )
        identifiers = (
            self.provider,
            self.default_generation_model,
            self.default_embedding_model,
        )
        if any(value is not None and not value.strip() for value in identifiers):
            raise AiConfigurationError("Local-AI identifiers must not be blank.")
        if self.automatically_download_models:
            raise AiConfigurationError("Automatic model downloads are prohibited.")
        if self.allow_remote_endpoints:
            raise AiConfigurationError("Remote AI endpoints are not available.")
        if not self.allow_only_loopback_endpoints:
            raise AiConfigurationError("Local AI must remain loopback-only.")
        if self.enable_conversation_persistence:
            raise AiConfigurationError(
                "Hidden AI conversation persistence is disabled."
            )
        if self.log_prompts or self.log_responses or self.expose_model_debug_output:
            raise AiConfigurationError(
                "Private AI content and debug output are not logged."
            )
        if self.endpoint is not None:
            self._validate_endpoint(self.endpoint)
        if self.enabled and self.provider is None:
            raise AiConfigurationError(
                "Enabled local AI requires a provider identifier."
            )

    @staticmethod
    def _validate_endpoint(value: str) -> None:
        parsed = urlsplit(value)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise AiConfigurationError("The local AI endpoint URL is invalid.")
        if parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise AiConfigurationError(
                "The local AI endpoint must not contain secrets."
            )
        host = parsed.hostname.casefold().rstrip(".")
        if host == "localhost":
            return
        try:
            if ipaddress.ip_address(host).is_loopback:
                return
        except ValueError:
            pass
        raise AiConfigurationError("The local AI endpoint must use a loopback address.")
