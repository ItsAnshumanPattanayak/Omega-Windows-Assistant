"""Unicode-safe command normalization without altering stored user content."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

from omega.core.exceptions import UnicodeSafetyError

_BIDI = frozenset(chr(value) for value in range(0x202A, 0x202F)) | frozenset(
    chr(value) for value in range(0x2066, 0x206A)
)
_ZERO_WIDTH = frozenset({"\u200b", "\u200c", "\u200d", "\u2060", "\ufeff"})


@dataclass(frozen=True, slots=True)
class NormalizedText:
    text: str
    removed_zero_width: bool = False
    safety_ambiguous: bool = False


def normalize_command_text(
    value: str, *, safety_sensitive: bool = False
) -> NormalizedText:
    """Return NFKC matching text and reject controls used for command obfuscation."""

    if "\x00" in value:
        raise UnicodeSafetyError("Null bytes are not allowed in commands.")
    if any(character in _BIDI for character in value):
        raise UnicodeSafetyError(
            "Bidirectional override controls are not allowed in commands."
        )
    for character in value:
        category = unicodedata.category(character)
        if category == "Cc" and character not in "\t\r\n":
            raise UnicodeSafetyError("Control characters are not allowed in commands.")
    removed = any(character in _ZERO_WIDTH for character in value)
    visible = "".join(character for character in value if character not in _ZERO_WIDTH)
    normalized = unicodedata.normalize("NFKC", visible)
    normalized = re.sub(r"\s+", " ", normalized).strip().casefold()
    return NormalizedText(
        normalized,
        removed_zero_width=removed,
        safety_ambiguous=removed and safety_sensitive,
    )


def terminal_safe_text(value: str, *, unicode_symbols: bool = True) -> str:
    """Provide deterministic ASCII fallbacks for decorative symbols only."""

    if unicode_symbols:
        return value
    for source, replacement in (
        ("✓", "OK"),
        ("⚠", "Warning"),
        ("✗", "Error"),
        ("—", "-"),
    ):
        value = value.replace(source, replacement)
    return value
