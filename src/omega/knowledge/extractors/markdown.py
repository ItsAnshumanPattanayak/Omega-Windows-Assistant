"""Markdown extraction that preserves markup and code as inert text."""

from __future__ import annotations

import re
from pathlib import Path

from omega.knowledge.configuration import KnowledgeConfiguration
from omega.knowledge.enums import KnowledgeSourceType
from omega.knowledge.exceptions import DocumentExtractionError
from omega.knowledge.extractors.base import normalize_text, title_from_path
from omega.knowledge.models import DocumentExtractionResult, ExtractedSegment

_HEADING = re.compile(r"^\s{0,3}#{1,6}\s+(.+?)\s*#*\s*$")


class MarkdownExtractor:
    name = "omega_markdown_text"

    def __init__(self, configuration: KnowledgeConfiguration) -> None:
        self.configuration = configuration

    def extract(self, path: Path, fingerprint: str) -> DocumentExtractionResult:
        try:
            raw = path.read_text(encoding="utf-8-sig")
        except (OSError, UnicodeError) as error:
            raise DocumentExtractionError(
                "The Markdown document is not UTF-8."
            ) from error
        if "\x00" in raw:
            raise DocumentExtractionError("The Markdown document appears binary.")
        segments: list[ExtractedSegment] = []
        heading: str | None = None
        buffer: list[str] = []
        title = title_from_path(path)
        for line in raw.replace("\r\n", "\n").replace("\r", "\n").splitlines():
            match = _HEADING.match(line)
            if match:
                self._append(segments, buffer, heading)
                heading = match.group(1).strip()[:300]
                if not segments and title == title_from_path(path):
                    title = heading
                buffer = [line]
            else:
                buffer.append(line)
        self._append(segments, buffer, heading)
        if not segments:
            raise DocumentExtractionError("No usable Markdown text was found.")
        text = "\n\n".join(item.text for item in segments)
        if len(text) > self.configuration.maximum_document_characters:
            raise DocumentExtractionError(
                "The Markdown document exceeds the text limit."
            )
        return DocumentExtractionResult(
            title,
            text,
            path.name,
            KnowledgeSourceType.MARKDOWN,
            fingerprint,
            self.name,
            tuple(segments),
            section_count=sum(1 for item in segments if item.section_title is not None),
        )

    @staticmethod
    def _append(
        segments: list[ExtractedSegment], buffer: list[str], heading: str | None
    ) -> None:
        text = normalize_text("\n".join(buffer))
        if text:
            segments.append(ExtractedSegment(text, section_title=heading))
