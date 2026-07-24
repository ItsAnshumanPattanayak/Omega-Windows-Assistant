from __future__ import annotations

import zipfile
from pathlib import Path

import pytest
from pypdf import PdfWriter
from pypdf.generic import (
    DecodedStreamObject,
    DictionaryObject,
    NameObject,
)

from omega.database import (
    DatabaseConfiguration,
    DatabaseConnectionFactory,
    MigrationRunner,
)
from omega.knowledge import (
    DeterministicChunker,
    KnowledgeConfiguration,
    KnowledgeRepository,
    KnowledgeService,
    KnowledgeSourceType,
)
from omega.knowledge.extractors import (
    DocxExtractor,
    ExtractorRegistry,
    MarkdownExtractor,
    PdfExtractor,
    TextExtractor,
)
from omega.knowledge.semantic_search import UnavailableSemanticSearch
from omega.knowledge.validation import KnowledgeFileValidator


def write_pdf(
    path: Path, text: str = "Gradient descent reduces a loss function."
) -> None:
    writer = PdfWriter()
    page = writer.add_blank_page(width=612, height=792)
    font = DictionaryObject(
        {
            NameObject("/Type"): NameObject("/Font"),
            NameObject("/Subtype"): NameObject("/Type1"),
            NameObject("/BaseFont"): NameObject("/Helvetica"),
        }
    )
    font_ref = writer._add_object(font)
    page[NameObject("/Resources")] = DictionaryObject(
        {NameObject("/Font"): DictionaryObject({NameObject("/F1"): font_ref})}
    )
    stream = DecodedStreamObject()
    safe = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    stream.set_data(f"BT /F1 12 Tf 72 720 Td ({safe}) Tj ET".encode("ascii"))
    page[NameObject("/Contents")] = writer._add_object(stream)
    with path.open("wb") as output:
        writer.write(output)


def write_docx(
    path: Path, text: str = "Database normalization avoids anomalies."
) -> None:
    document = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/'
        'wordprocessingml/2006/main"><w:body>'
        f"<w:p><w:r><w:t>{text}</w:t></w:r></w:p>"
        "</w:body></w:document>"
    )
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("word/document.xml", document)


@pytest.fixture
def knowledge(
    tmp_path: Path,
) -> tuple[KnowledgeService, KnowledgeRepository, KnowledgeConfiguration]:
    configuration = KnowledgeConfiguration()
    factory = DatabaseConnectionFactory(
        DatabaseConfiguration(), database_path=tmp_path / "omega.db"
    )
    MigrationRunner(factory).migrate()
    repository = KnowledgeRepository(factory)
    registry = ExtractorRegistry(
        {
            KnowledgeSourceType.TEXT: TextExtractor(configuration),
            KnowledgeSourceType.MARKDOWN: MarkdownExtractor(configuration),
            KnowledgeSourceType.DOCX: DocxExtractor(configuration),
            KnowledgeSourceType.PDF: PdfExtractor(configuration),
        }
    )
    service = KnowledgeService(
        configuration,
        repository,
        KnowledgeFileValidator(configuration, (tmp_path,)),
        registry,
        DeterministicChunker(configuration),
        UnavailableSemanticSearch(),
    )
    return service, repository, configuration
