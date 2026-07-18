"""Conservative text normalization that preserves names and path syntax."""

from __future__ import annotations

import re


class CommandNormalizer:
    """Normalize command matching text without changing the original input."""

    _SMART_QUOTES = str.maketrans({"“": '"', "”": '"', "‘": "'", "’": "'"})

    def normalize(self, text: str) -> str:
        """Return deterministic, case-folded matching text."""
        normalized = re.sub(r"\s+", " ", text.translate(self._SMART_QUOTES).strip())
        if normalized.endswith(("?", "!")):
            normalized = normalized[:-1].rstrip()
        elif normalized.endswith(".") and not re.search(
            r"\.[A-Za-z0-9]+\.$", normalized
        ):
            normalized = normalized[:-1].rstrip()
        return normalized.casefold()
