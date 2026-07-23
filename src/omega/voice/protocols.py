"""Dependency-injection contracts for local voice adapters."""

from __future__ import annotations

from collections.abc import Callable
from typing import Protocol

from omega.voice.models import AudioDevice, TranscriptionResult, VoiceEvent


class AudioSource(Protocol):
    """A cancellable source of bounded PCM audio blocks."""

    def start(self) -> None: ...

    def read(self, timeout_seconds: float) -> bytes | None: ...

    def stop(self) -> None: ...

    def list_devices(self) -> tuple[AudioDevice, ...]: ...


class SpeechRecognizer(Protocol):
    """Convert one audio block to text without interpreting commands."""

    def transcribe(self, audio: bytes) -> TranscriptionResult | None: ...

    def close(self) -> None: ...


class SpeechSynthesizer(Protocol):
    """Queue safe local speech output."""

    def start(self) -> None: ...

    def speak(self, text: str) -> bool: ...

    def cancel(self) -> None: ...

    def close(self) -> None: ...


VoiceEventSink = Callable[[VoiceEvent], None]
