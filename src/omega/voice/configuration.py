"""Strict configuration for Omega's optional offline voice adapter."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from omega.core.exceptions import VoiceConfigurationError

_ALLOWED_KEYS = frozenset(
    {
        "enabled",
        "offline_recognition_enabled",
        "model_path",
        "microphone_device",
        "sample_rate_hz",
        "audio_block_size",
        "passive_listening_timeout_seconds",
        "active_listening_timeout_seconds",
        "active_session_timeout_seconds",
        "maximum_transcript_characters",
        "minimum_confidence",
        "speak_responses",
        "speech_rate",
        "speech_volume",
        "voice_name",
        "confirmation_confidence_threshold",
        "return_to_passive_after_session",
    }
)


@dataclass(frozen=True)
class VoiceConfiguration:
    """Validated, side-effect-free settings for one voice service."""

    enabled: bool
    wake_phrase: str
    shutdown_phrase: str
    offline_recognition_enabled: bool
    model_path: Path | None
    microphone_device: int | str | None
    sample_rate_hz: int
    audio_block_size: int
    passive_listening_timeout_seconds: float
    active_listening_timeout_seconds: float
    active_session_timeout_seconds: float
    maximum_transcript_characters: int
    minimum_confidence: float
    speak_responses: bool
    speech_rate: int
    speech_volume: float
    voice_name: str | None
    confirmation_confidence_threshold: float
    return_to_passive_after_session: bool

    @classmethod
    def from_mapping(
        cls,
        values: Mapping[str, Any],
        *,
        wake_phrase: str,
        shutdown_phrase: str,
        model_root: Path,
    ) -> VoiceConfiguration:
        """Build a strict configuration without touching devices or models."""

        unknown = set(values).difference(_ALLOWED_KEYS)
        if unknown:
            raise VoiceConfigurationError(
                "Unknown voice setting(s): " + ", ".join(sorted(unknown))
            )
        wake = cls._text(wake_phrase, "assistant.activation_phrase")
        shutdown = cls._text(shutdown_phrase, "assistant.shutdown_phrase")
        if cls._phrase_key(wake) == cls._phrase_key(shutdown):
            raise VoiceConfigurationError(
                "Voice wake and shutdown phrases must be different."
            )

        device = values.get("microphone_device")
        if device is not None and (
            isinstance(device, bool) or not isinstance(device, (int, str))
        ):
            raise VoiceConfigurationError(
                "voice.microphone_device must be an integer, string, or null."
            )
        if isinstance(device, int) and device < 0:
            raise VoiceConfigurationError(
                "voice.microphone_device index must be non-negative."
            )
        if isinstance(device, str):
            device = cls._text(device, "voice.microphone_device")

        model_path = cls._model_path(values.get("model_path"), model_root)
        voice_name = values.get("voice_name")
        if voice_name is not None:
            voice_name = cls._text(voice_name, "voice.voice_name")

        minimum = cls._number(
            values.get("minimum_confidence", 0.5),
            "voice.minimum_confidence",
            0.0,
            1.0,
        )
        strict = cls._number(
            values.get("confirmation_confidence_threshold", 0.85),
            "voice.confirmation_confidence_threshold",
            0.0,
            1.0,
        )
        if strict < minimum:
            raise VoiceConfigurationError(
                "voice.confirmation_confidence_threshold must be at least "
                "voice.minimum_confidence."
            )

        return cls(
            enabled=cls._boolean(values.get("enabled", False), "voice.enabled"),
            wake_phrase=wake,
            shutdown_phrase=shutdown,
            offline_recognition_enabled=cls._boolean(
                values.get("offline_recognition_enabled", True),
                "voice.offline_recognition_enabled",
            ),
            model_path=model_path,
            microphone_device=device,
            sample_rate_hz=cls._integer(
                values.get("sample_rate_hz", 16_000),
                "voice.sample_rate_hz",
                8_000,
                96_000,
            ),
            audio_block_size=cls._integer(
                values.get("audio_block_size", 4_000),
                "voice.audio_block_size",
                256,
                65_536,
            ),
            passive_listening_timeout_seconds=cls._number(
                values.get("passive_listening_timeout_seconds", 1),
                "voice.passive_listening_timeout_seconds",
                0.05,
                60.0,
            ),
            active_listening_timeout_seconds=cls._number(
                values.get("active_listening_timeout_seconds", 10),
                "voice.active_listening_timeout_seconds",
                0.1,
                120.0,
            ),
            active_session_timeout_seconds=cls._number(
                values.get("active_session_timeout_seconds", 300),
                "voice.active_session_timeout_seconds",
                1.0,
                86_400.0,
            ),
            maximum_transcript_characters=cls._integer(
                values.get("maximum_transcript_characters", 1_000),
                "voice.maximum_transcript_characters",
                1,
                10_000,
            ),
            minimum_confidence=minimum,
            speak_responses=cls._boolean(
                values.get("speak_responses", True),
                "voice.speak_responses",
            ),
            speech_rate=cls._integer(
                values.get("speech_rate", 180),
                "voice.speech_rate",
                80,
                400,
            ),
            speech_volume=cls._number(
                values.get("speech_volume", 1.0),
                "voice.speech_volume",
                0.0,
                1.0,
            ),
            voice_name=voice_name,
            confirmation_confidence_threshold=strict,
            return_to_passive_after_session=cls._boolean(
                values.get("return_to_passive_after_session", True),
                "voice.return_to_passive_after_session",
            ),
        )

    @staticmethod
    def _phrase_key(value: str) -> str:
        return " ".join(value.casefold().split())

    @staticmethod
    def _text(value: object, name: str) -> str:
        if not isinstance(value, str) or not value.strip():
            raise VoiceConfigurationError(f"{name} must be a non-empty string.")
        return value.strip()

    @staticmethod
    def _boolean(value: object, name: str) -> bool:
        if not isinstance(value, bool):
            raise VoiceConfigurationError(f"{name} must be a boolean.")
        return value

    @staticmethod
    def _integer(value: object, name: str, minimum: int, maximum: int) -> int:
        if (
            isinstance(value, bool)
            or not isinstance(value, int)
            or not minimum <= value <= maximum
        ):
            raise VoiceConfigurationError(
                f"{name} must be an integer between {minimum} and {maximum}."
            )
        return value

    @staticmethod
    def _number(
        value: object,
        name: str,
        minimum: float,
        maximum: float,
    ) -> float:
        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not minimum <= float(value) <= maximum
        ):
            raise VoiceConfigurationError(
                f"{name} must be between {minimum} and {maximum}."
            )
        return float(value)

    @staticmethod
    def _model_path(value: object, model_root: Path) -> Path | None:
        if value is None:
            return None
        if not isinstance(value, str) or not value.strip():
            raise VoiceConfigurationError(
                "voice.model_path must be a non-empty relative path or null."
            )
        supplied = Path(value)
        if supplied.is_absolute() or ".." in supplied.parts:
            raise VoiceConfigurationError(
                "voice.model_path must remain within data/voice_models."
            )
        root = model_root.resolve(strict=False)
        resolved = (root / supplied).resolve(strict=False)
        try:
            resolved.relative_to(root)
        except ValueError as error:
            raise VoiceConfigurationError(
                "voice.model_path must remain within data/voice_models."
            ) from error
        return resolved
