"""Typed data and lifecycle state for optional voice interaction."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from threading import Lock
from typing import Any
from uuid import UUID, uuid4

from omega.core.exceptions import ModelValidationError, VoiceStateError


class VoiceState(StrEnum):
    """Observable lifecycle states for one explicitly started voice service."""

    DISABLED = "disabled"
    UNAVAILABLE = "unavailable"
    IDLE = "idle"
    PASSIVE_LISTENING = "passive_listening"
    WAKE_DETECTED = "wake_detected"
    ACTIVE_LISTENING = "active_listening"
    TRANSCRIBING = "transcribing"
    PROCESSING_COMMAND = "processing_command"
    AWAITING_CONFIRMATION = "awaiting_confirmation"
    SPEAKING = "speaking"
    STOPPING = "stopping"
    ERROR = "error"


_TRANSITIONS: dict[VoiceState, frozenset[VoiceState]] = {
    VoiceState.DISABLED: frozenset({VoiceState.IDLE}),
    VoiceState.UNAVAILABLE: frozenset({VoiceState.IDLE}),
    VoiceState.IDLE: frozenset(
        {
            VoiceState.PASSIVE_LISTENING,
            VoiceState.STOPPING,
            VoiceState.UNAVAILABLE,
            VoiceState.ERROR,
        }
    ),
    VoiceState.PASSIVE_LISTENING: frozenset(
        {
            VoiceState.TRANSCRIBING,
            VoiceState.WAKE_DETECTED,
            VoiceState.STOPPING,
            VoiceState.ERROR,
        }
    ),
    VoiceState.WAKE_DETECTED: frozenset(
        {
            VoiceState.PROCESSING_COMMAND,
            VoiceState.ACTIVE_LISTENING,
            VoiceState.STOPPING,
            VoiceState.ERROR,
        }
    ),
    VoiceState.ACTIVE_LISTENING: frozenset(
        {
            VoiceState.TRANSCRIBING,
            VoiceState.PROCESSING_COMMAND,
            VoiceState.PASSIVE_LISTENING,
            VoiceState.STOPPING,
            VoiceState.ERROR,
        }
    ),
    VoiceState.TRANSCRIBING: frozenset(
        {
            VoiceState.PASSIVE_LISTENING,
            VoiceState.WAKE_DETECTED,
            VoiceState.ACTIVE_LISTENING,
            VoiceState.PROCESSING_COMMAND,
            VoiceState.AWAITING_CONFIRMATION,
            VoiceState.STOPPING,
            VoiceState.ERROR,
        }
    ),
    VoiceState.PROCESSING_COMMAND: frozenset(
        {
            VoiceState.ACTIVE_LISTENING,
            VoiceState.AWAITING_CONFIRMATION,
            VoiceState.SPEAKING,
            VoiceState.PASSIVE_LISTENING,
            VoiceState.STOPPING,
            VoiceState.ERROR,
        }
    ),
    VoiceState.AWAITING_CONFIRMATION: frozenset(
        {
            VoiceState.TRANSCRIBING,
            VoiceState.PROCESSING_COMMAND,
            VoiceState.SPEAKING,
            VoiceState.ACTIVE_LISTENING,
            VoiceState.STOPPING,
            VoiceState.ERROR,
        }
    ),
    VoiceState.SPEAKING: frozenset(
        {
            VoiceState.ACTIVE_LISTENING,
            VoiceState.AWAITING_CONFIRMATION,
            VoiceState.PASSIVE_LISTENING,
            VoiceState.STOPPING,
            VoiceState.ERROR,
        }
    ),
    VoiceState.STOPPING: frozenset({VoiceState.IDLE, VoiceState.ERROR}),
    VoiceState.ERROR: frozenset(
        {VoiceState.IDLE, VoiceState.STOPPING, VoiceState.UNAVAILABLE}
    ),
}


class VoiceStateMachine:
    """Thread-safe validator for voice state transitions."""

    def __init__(self, initial: VoiceState = VoiceState.IDLE) -> None:
        self._state = initial
        self._lock = Lock()

    @property
    def state(self) -> VoiceState:
        with self._lock:
            return self._state

    def transition_to(self, target: VoiceState) -> VoiceState:
        with self._lock:
            if target is self._state:
                return self._state
            if target not in _TRANSITIONS[self._state]:
                raise VoiceStateError(
                    f"Cannot transition voice from {self._state.value} "
                    f"to {target.value}."
                )
            self._state = target
            return target


@dataclass(frozen=True)
class TranscriptionResult:
    """One final or partial result returned by an offline recognizer."""

    transcript: str
    normalized_transcript: str
    confidence: float
    is_final: bool
    started_at: datetime
    completed_at: datetime
    duration_ms: int
    recognizer_name: str
    result_id: UUID = field(default_factory=uuid4)
    metadata: dict[str, str | int | float | bool | None] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.transcript, str):
            raise ModelValidationError("transcript must be a string.")
        if not isinstance(self.normalized_transcript, str):
            raise ModelValidationError("normalized_transcript must be a string.")
        if (
            isinstance(self.confidence, bool)
            or not isinstance(self.confidence, (int, float))
            or not 0.0 <= float(self.confidence) <= 1.0
        ):
            raise ModelValidationError("transcription confidence must be 0.0 to 1.0.")
        if not isinstance(self.is_final, bool):
            raise ModelValidationError("is_final must be a boolean.")
        for timestamp, name in (
            (self.started_at, "started_at"),
            (self.completed_at, "completed_at"),
        ):
            if timestamp.tzinfo is None or timestamp.utcoffset() is None:
                raise ModelValidationError(f"{name} must be timezone-aware.")
        if self.completed_at < self.started_at:
            raise ModelValidationError("completed_at must not precede started_at.")
        if (
            isinstance(self.duration_ms, bool)
            or not isinstance(self.duration_ms, int)
            or self.duration_ms < 0
        ):
            raise ModelValidationError("duration_ms must be non-negative.")
        if (
            not isinstance(self.recognizer_name, str)
            or not self.recognizer_name.strip()
        ):
            raise ModelValidationError("recognizer_name must be non-empty.")

    @classmethod
    def now(
        cls,
        transcript: str,
        normalized_transcript: str,
        confidence: float,
        *,
        is_final: bool = True,
        recognizer_name: str = "fake",
        result_id: UUID | None = None,
    ) -> TranscriptionResult:
        """Create a deterministic-friendly instantaneous result."""

        timestamp = datetime.now(UTC)
        return cls(
            transcript,
            normalized_transcript,
            confidence,
            is_final,
            timestamp,
            timestamp,
            0,
            recognizer_name,
            result_id=result_id or uuid4(),
        )


@dataclass(frozen=True)
class AudioDevice:
    """Safe public metadata for one microphone-capable input device."""

    identifier: int
    name: str
    input_channels: int
    default_sample_rate_hz: int


@dataclass(frozen=True)
class VoiceEvent:
    """Thread-neutral update for terminal and GUI adapters."""

    state: VoiceState
    message: str = ""
    transcript: str | None = None
    response: str | None = None
    occurred_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        if self.occurred_at.tzinfo is None or self.occurred_at.utcoffset() is None:
            raise ModelValidationError("Voice event timestamp must be timezone-aware.")
        if not all(
            value is None or isinstance(value, str)
            for value in (self.transcript, self.response)
        ):
            raise ModelValidationError("Voice event text must be strings or null.")

    def to_dict(self) -> dict[str, Any]:
        """Return JSON-compatible event data for presentation adapters."""

        return {
            "state": self.state.value,
            "message": self.message,
            "transcript": self.transcript,
            "response": self.response,
            "occurred_at": self.occurred_at.isoformat(),
        }
