import zipfile
from pathlib import Path

import pytest
from pypdf import PdfWriter

from omega.knowledge import KnowledgeConfiguration, KnowledgeSourceType
from omega.knowledge.exceptions import (
    DocumentExtractionError,
    DocumentValidationError,
    UnsupportedDocumentError,
)
from omega.knowledge.extractors import (
    DocxExtractor,
    MarkdownExtractor,
    PdfExtractor,
    TextExtractor,
)
from omega.knowledge.validation import KnowledgeFileValidator
from tests.knowledge.conftest import write_docx, write_pdf


def test_txt_and_markdown_are_inert_bounded_text(tmp_path: Path) -> None:
    text_path = tmp_path / "notes.txt"
    text_path.write_text("First paragraph.\r\n\r\nSecond paragraph.", encoding="utf-8")
    markdown_path = tmp_path / "guide.md"
    markdown_path.write_text(
        "# Safety\n\n```powershell\nRemove-Item C:\\\\\n```\n"
        "[do not open](https://example.com)",
        encoding="utf-8",
    )
    validator = KnowledgeFileValidator(KnowledgeConfiguration(), (tmp_path,))
    text_file = validator.validate(text_path)
    md_file = validator.validate(markdown_path)
    text = TextExtractor(KnowledgeConfiguration()).extract(
        text_file.path, text_file.fingerprint
    )
    markdown = MarkdownExtractor(KnowledgeConfiguration()).extract(
        md_file.path, md_file.fingerprint
    )
    assert text.text == "First paragraph.\n\nSecond paragraph."
    assert "Remove-Item" in markdown.text
    assert "https://example.com" in markdown.text
    assert markdown.segments[0].section_title == "Safety"


def test_pdf_and_docx_extract_real_text_without_embedded_execution(
    tmp_path: Path,
) -> None:
    pdf_path = tmp_path / "course.pdf"
    docx_path = tmp_path / "database.docx"
    write_pdf(pdf_path)
    write_docx(docx_path)
    validator = KnowledgeFileValidator(KnowledgeConfiguration(), (tmp_path,))
    pdf = validator.validate(pdf_path)
    docx = validator.validate(docx_path)
    pdf_result = PdfExtractor(KnowledgeConfiguration()).extract(
        pdf.path, pdf.fingerprint
    )
    docx_result = DocxExtractor(KnowledgeConfiguration()).extract(
        docx.path, docx.fingerprint
    )
    assert pdf_result.source_type is KnowledgeSourceType.PDF
    assert "Gradient descent" in pdf_result.text
    assert pdf_result.segments[0].page_number == 1
    assert "normalization" in docx_result.text


def test_validation_rejects_unsafe_paths_and_formats(tmp_path: Path) -> None:
    validator = KnowledgeFileValidator(KnowledgeConfiguration(), (tmp_path,))
    executable = tmp_path / "run.exe"
    executable.write_bytes(b"MZ")
    with pytest.raises(UnsupportedDocumentError):
        validator.validate(executable)
    binary = tmp_path / "binary.txt"
    binary.write_bytes(b"a\x00b")
    with pytest.raises(DocumentValidationError):
        validator.validate(binary)
    outside = tmp_path.parent / "outside.txt"
    outside.write_text("private", encoding="utf-8")
    with pytest.raises(DocumentValidationError):
        validator.validate(outside)
    directory = tmp_path / "folder.txt"
    directory.mkdir()
    with pytest.raises(DocumentValidationError):
        validator.validate(directory)


def test_empty_and_macro_enabled_documents_fail_safely(tmp_path: Path) -> None:
    empty = tmp_path / "empty.txt"
    empty.write_text("   ", encoding="utf-8")
    validated = KnowledgeFileValidator(KnowledgeConfiguration(), (tmp_path,)).validate(
        empty
    )
    with pytest.raises(DocumentExtractionError):
        TextExtractor(KnowledgeConfiguration()).extract(
            validated.path, validated.fingerprint
        )
    macro = tmp_path / "macro.docx"
    with zipfile.ZipFile(macro, "w") as archive:
        archive.writestr(
            "word/document.xml",
            '<w:document xmlns:w="http://schemas.openxmlformats.org/'
            'wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>'
            "Never run macros</w:t></w:r></w:p></w:body></w:document>",
        )
        archive.writestr("word/vbaProject.bin", b"macro")
    macro_file = KnowledgeFileValidator(KnowledgeConfiguration(), (tmp_path,)).validate(
        macro
    )
    with pytest.raises(DocumentExtractionError):
        DocxExtractor(KnowledgeConfiguration()).extract(
            macro_file.path, macro_file.fingerprint
        )


def test_encrypted_pdf_and_missing_file_fail_safely(tmp_path: Path) -> None:
    encrypted = tmp_path / "encrypted.pdf"
    writer = PdfWriter()
    writer.add_blank_page(width=100, height=100)
    writer.encrypt("password")
    with encrypted.open("wb") as output:
        writer.write(output)
    validator = KnowledgeFileValidator(KnowledgeConfiguration(), (tmp_path,))
    validated = validator.validate(encrypted)
    with pytest.raises(DocumentExtractionError):
        PdfExtractor(KnowledgeConfiguration()).extract(
            validated.path, validated.fingerprint
        )
    with pytest.raises(DocumentValidationError):
        validator.validate(tmp_path / "missing.pdf")
