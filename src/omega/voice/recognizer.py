"""Vosk-backed offline speech-to-text adapter."""

from __future__ import annotations

import importlib
import json
from datetime import UTC, datetime
from pathlib import Path
from types import ModuleType
from typing import Any

from omega.core.exceptions import RecognitionError, VoiceInitializationError
from omega.understanding.normalizer import CommandNormalizer
from omega.voice.models import TranscriptionResult


class VoskSpeechRecognizer:
    """Transcribe PCM audio using a preinstalled local Vosk model."""

    def __init__(
        self,
        model_path: Path | None,
        *,
        sample_rate_hz: int,
        maximum_characters: int,
    ) -> None:
        if model_path is None:
            raise VoiceInitializationError(
                "No offline speech model is configured. Place a Vosk model under "
                "data/voice_models and set voice.model_path."
            )
        if not model_path.is_dir():
            raise VoiceInitializationError(
                "The configured offline speech model is missing or invalid."
            )
        self.model_path = model_path
        self.sample_rate_hz = sample_rate_hz
        self.maximum_characters = maximum_characters
        self._normalizer = CommandNormalizer()
        module = self._module()
        try:
            model = module.Model(str(model_path))
            recognizer = module.KaldiRecognizer(model, sample_rate_hz)
            recognizer.SetWords(True)
        except Exception as error:
            raise VoiceInitializationError(
                "Omega could not initialize the configured offline speech model."
            ) from error
        self._model: Any = model
        self._recognizer: Any = recognizer

    @staticmethod
    def _module() -> ModuleType:
        try:
            return importlib.import_module("vosk")
        except (ImportError, OSError) as error:
            raise VoiceInitializationError(
                "Offline recognition is unavailable. Install Omega with the "
                "voice extra: pip install -e .[voice]"
            ) from error

    def transcribe(self, audio: bytes) -> TranscriptionResult | None:
        """Return only complete bounded recognition results."""

        if not isinstance(audio, bytes) or not audio:
            raise RecognitionError("Recognition requires non-empty PCM audio.")
        started = datetime.now(UTC)
        try:
            if not bool(self._recognizer.AcceptWaveform(audio)):
                return None
            payload = json.loads(self._recognizer.Result())
        except (TypeError, ValueError, json.JSONDecodeError, RuntimeError) as error:
            raise RecognitionError(
                "Offline speech recognition failed safely."
            ) from error
        transcript = str(payload.get("text", "")).strip()
        if not transcript:
            return None
        if len(transcript) > self.maximum_characters:
            raise RecognitionError("The recognized transcript is too long.")
        words = payload.get("result", [])
        confidences = [
            float(word["conf"])
            for word in words
            if isinstance(word, dict)
            and isinstance(word.get("conf"), (int, float))
            and not isinstance(word.get("conf"), bool)
        ]
        confidence = sum(confidences) / len(confidences) if confidences else 0.0
        completed = datetime.now(UTC)
        return TranscriptionResult(
            transcript=transcript,
            normalized_transcript=self._normalizer.normalize(transcript),
            confidence=max(0.0, min(1.0, confidence)),
            is_final=True,
            started_at=started,
            completed_at=completed,
            duration_ms=max(0, int((completed - started).total_seconds() * 1_000)),
            recognizer_name="vosk",
        )

    def close(self) -> None:
        """Release model references without persisting audio."""

        self._recognizer = None
        self._model = None
