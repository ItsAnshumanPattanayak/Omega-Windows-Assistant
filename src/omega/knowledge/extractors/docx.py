"""Macro-free DOCX paragraph and table extraction using bounded ZIP/XML parsing."""

from __future__ import annotations

import zipfile
from pathlib import Path
from xml.etree import ElementTree

from omega.knowledge.configuration import KnowledgeConfiguration
from omega.knowledge.enums import KnowledgeSourceType
from omega.knowledge.exceptions import DocumentExtractionError
from omega.knowledge.extractors.base import normalize_text, title_from_path
from omega.knowledge.models import DocumentExtractionResult, ExtractedSegment

_W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
_DOCUMENT = "word/document.xml"


class DocxExtractor:
    name = "omega_docx_xml"

    def __init__(self, configuration: KnowledgeConfiguration) -> None:
        self.configuration = configuration

    def extract(self, path: Path, fingerprint: str) -> DocumentExtractionResult:
        try:
            with zipfile.ZipFile(path) as archive:
                names = archive.namelist()
                if len(names) > 10_000 or _DOCUMENT not in names:
                    raise DocumentExtractionError("The DOCX container is malformed.")
                if any(name.casefold().endswith("vbaproject.bin") for name in names):
                    raise DocumentExtractionError(
                        "Macro-enabled Word documents are not supported."
                    )
                info = archive.getinfo(_DOCUMENT)
                if info.file_size > self.configuration.maximum_file_bytes * 4:
                    raise DocumentExtractionError("The DOCX XML is too large.")
                root = ElementTree.fromstring(archive.read(_DOCUMENT))
        except DocumentExtractionError:
            raise
        except (OSError, zipfile.BadZipFile, KeyError, ElementTree.ParseError) as error:
            raise DocumentExtractionError("The DOCX document is malformed.") from error
        segments: list[ExtractedSegment] = []
        current_heading: str | None = None
        for paragraph in root.iter(f"{_W}p"):
            text = normalize_text(
                "".join(node.text or "" for node in paragraph.iter(f"{_W}t"))
            )
            if not text:
                continue
            style = paragraph.find(f".//{_W}pStyle")
            style_name = style.get(f"{_W}val", "") if style is not None else ""
            if style_name.casefold().startswith("heading"):
                current_heading = text[:300]
            segments.append(ExtractedSegment(text, section_title=current_heading))
        if not segments:
            raise DocumentExtractionError("No usable text was found in the DOCX file.")
        text = "\n\n".join(item.text for item in segments)
        if len(text) > self.configuration.maximum_document_characters:
            raise DocumentExtractionError("The DOCX document exceeds the text limit.")
        title = next(
            (item.section_title for item in segments if item.section_title),
            title_from_path(path),
        )
        return DocumentExtractionResult(
            title,
            text,
            path.name,
            KnowledgeSourceType.DOCX,
            fingerprint,
            self.name,
            tuple(segments),
            section_count=len(
                {item.section_title for item in segments if item.section_title}
            ),
        )
