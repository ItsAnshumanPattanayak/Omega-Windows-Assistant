"""Text-only PDF extraction; images, scripts, links, and attachments stay untouched."""

from __future__ import annotations

from pathlib import Path

from omega.knowledge.configuration import KnowledgeConfiguration
from omega.knowledge.enums import KnowledgeSourceType
from omega.knowledge.exceptions import DocumentExtractionError
from omega.knowledge.extractors.base import normalize_text, title_from_path
from omega.knowledge.models import DocumentExtractionResult, ExtractedSegment


class PdfExtractor:
    name = "pypdf_text"

    def __init__(self, configuration: KnowledgeConfiguration) -> None:
        self.configuration = configuration

    def extract(self, path: Path, fingerprint: str) -> DocumentExtractionResult:
        try:
            from pypdf import PdfReader
            from pypdf.errors import PdfReadError
        except ImportError as error:
            raise DocumentExtractionError(
                "PDF support requires the installed pypdf dependency."
            ) from error
        try:
            reader = PdfReader(path, strict=True)
            if reader.is_encrypted:
                raise DocumentExtractionError(
                    "Encrypted or password-protected PDFs are not supported."
                )
            if len(reader.pages) > self.configuration.maximum_pages:
                raise DocumentExtractionError("The PDF exceeds the page limit.")
            segments: list[ExtractedSegment] = []
            characters = 0
            for number, page in enumerate(reader.pages, start=1):
                value = normalize_text(page.extract_text() or "")
                if not value:
                    continue
                characters += len(value)
                if characters > self.configuration.maximum_document_characters:
                    raise DocumentExtractionError("The PDF exceeds the text limit.")
                segments.append(ExtractedSegment(value, page_number=number))
        except DocumentExtractionError:
            raise
        except (OSError, PdfReadError, ValueError) as error:
            raise DocumentExtractionError(
                "The PDF could not be read safely."
            ) from error
        if not segments:
            raise DocumentExtractionError(
                "No usable PDF text was found; OCR is not available automatically."
            )
        text = "\n\n".join(item.text for item in segments)
        return DocumentExtractionResult(
            title_from_path(path),
            text,
            path.name,
            KnowledgeSourceType.PDF,
            fingerprint,
            self.name,
            tuple(segments),
            page_count=len(reader.pages),
        )
