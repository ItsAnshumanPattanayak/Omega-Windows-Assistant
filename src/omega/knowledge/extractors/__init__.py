"""Safe document extractor registry."""

from omega.knowledge.extractors.docx import DocxExtractor
from omega.knowledge.extractors.markdown import MarkdownExtractor
from omega.knowledge.extractors.pdf import PdfExtractor
from omega.knowledge.extractors.registry import ExtractorRegistry
from omega.knowledge.extractors.text import TextExtractor

__all__ = [
    "DocxExtractor",
    "ExtractorRegistry",
    "MarkdownExtractor",
    "PdfExtractor",
    "TextExtractor",
]
