"""Bounded UTF-8 plain-text extraction."""

from pathlib import Path

from omega.knowledge.configuration import KnowledgeConfiguration
from omega.knowledge.enums import KnowledgeSourceType
from omega.knowledge.exceptions import DocumentExtractionError
from omega.knowledge.extractors.base import title_from_path, validate_extracted_text
from omega.knowledge.models import DocumentExtractionResult, ExtractedSegment


class TextExtractor:
    name = "omega_text"

    def __init__(self, configuration: KnowledgeConfiguration) -> None:
        self.configuration = configuration

    def extract(self, path: Path, fingerprint: str) -> DocumentExtractionResult:
        try:
            value = path.read_text(encoding="utf-8-sig")
        except (OSError, UnicodeError) as error:
            raise DocumentExtractionError(
                "The text document is not valid bounded UTF-8."
            ) from error
        text = validate_extracted_text(
            value, self.configuration.maximum_document_characters
        )
        return DocumentExtractionResult(
            title_from_path(path),
            text,
            path.name,
            KnowledgeSourceType.TEXT,
            fingerprint,
            self.name,
            (ExtractedSegment(text),),
        )
