"""Shared bounded extraction helpers."""

from __future__ import annotations

import re
from pathlib import Path

from omega.knowledge.exceptions import DocumentExtractionError

_SPACE = re.compile(r"[ \t]+")
_BLANKS = re.compile(r"\n{3,}")


def normalize_text(value: str) -> str:
    value = value.replace("\r\n", "\n").replace("\r", "\n")
    lines = [_SPACE.sub(" ", line).rstrip() for line in value.split("\n")]
    return _BLANKS.sub("\n\n", "\n".join(lines)).strip()


def title_from_path(path: Path) -> str:
    title = path.stem.replace("_", " ").replace("-", " ").strip()
    return title[:300] or "Untitled document"


def validate_extracted_text(value: str, maximum: int) -> str:
    normalized = normalize_text(value)
    if not normalized:
        raise DocumentExtractionError(
            "No usable text was found; image-only documents require "
            "explicit OCR support."
        )
    if len(normalized) > maximum:
        raise DocumentExtractionError(
            "The extracted document exceeds Omega's configured text limit."
        )
    return normalized
