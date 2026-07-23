"""Strict deterministic matching for Omega's configured wake phrase."""

from __future__ import annotations

import re
from dataclasses import dataclass

_TRAILING_PUNCTUATION = re.compile(r"[\s,!.?;:]+$")
_LEADING_PUNCTUATION = re.compile(r"^[\s,!.?;:]+")
_WHITESPACE = re.compile(r"\s+")


def normalize_system_phrase(text: str) -> str:
    """Normalize casing, spacing, and harmless boundary punctuation only."""

    bounded = _LEADING_PUNCTUATION.sub("", text)
    bounded = _TRAILING_PUNCTUATION.sub("", bounded)
    return _WHITESPACE.sub(" ", bounded.strip()).casefold()


@dataclass(frozen=True)
class WakeMatch:
    """A strict wake result with an optional deterministic command remainder."""

    detected: bool
    command: str | None = None


class WakeWordDetector:
    """Detect an exact configured phrase or exact phrase prefix plus command."""

    def __init__(self, phrase: str, minimum_confidence: float) -> None:
        self.phrase = phrase.strip()
        self._normalized = normalize_system_phrase(phrase)
        self.minimum_confidence = minimum_confidence

    def detect(self, transcript: str, confidence: float) -> WakeMatch:
        if confidence < self.minimum_confidence:
            return WakeMatch(False)
        stripped = transcript.strip()
        if normalize_system_phrase(stripped) == self._normalized:
            return WakeMatch(True)

        escaped = re.escape(self.phrase)
        prefix = re.match(
            rf"^\s*{escaped}\s*[,;:]\s+(?P<command>.+?)\s*$",
            transcript,
            flags=re.IGNORECASE,
        )
        if prefix is None:
            return WakeMatch(False)
        command = prefix.group("command").strip()
        return WakeMatch(bool(command), command or None)
