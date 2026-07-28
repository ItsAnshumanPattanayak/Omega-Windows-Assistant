"""Offline voice-language compatibility and accessible preference helpers."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from omega.accessibility.models import LanguageIdentifier


@dataclass(frozen=True, slots=True)
class VoiceAccessibilityStatus:
    language: LanguageIdentifier
    recognition_reliable: bool
    warning: str | None = None


def voice_language_status(
    language: str, model_path: Path | None
) -> VoiceAccessibilityStatus:
    selected = LanguageIdentifier(language)
    if model_path is None:
        return VoiceAccessibilityStatus(
            selected,
            False,
            "No offline recognition model is configured; text mode remains available.",
        )
    marker = model_path.name.casefold().replace("_", "-")
    aliases = {"en": ("en", "english"), "hi": ("hi", "hindi")}
    compatible = any(value in marker for value in aliases.get(language, (language,)))
    return VoiceAccessibilityStatus(
        selected,
        compatible,
        (
            None
            if compatible
            else "The recognition language and configured Vosk model may not match; "
            "text mode remains available."
        ),
    )


def multilingual_confirmation_allowed(confidence: float, threshold: float) -> bool:
    return 0.0 <= confidence <= 1.0 and confidence >= threshold


def select_sapi_voice(requested: str | None, installed: tuple[str, ...]) -> str | None:
    if requested is None:
        return installed[0] if installed else None
    return next(
        (item for item in installed if item.casefold() == requested.casefold()), None
    )
