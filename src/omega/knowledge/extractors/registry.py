"""Explicit source-type to extractor mapping."""

from omega.knowledge.enums import KnowledgeSourceType
from omega.knowledge.exceptions import UnsupportedDocumentError
from omega.knowledge.protocols import DocumentExtractor


class ExtractorRegistry:
    def __init__(
        self, extractors: dict[KnowledgeSourceType, DocumentExtractor]
    ) -> None:
        self._extractors = dict(extractors)

    def require(self, source_type: KnowledgeSourceType) -> DocumentExtractor:
        extractor = self._extractors.get(source_type)
        if extractor is None:
            raise UnsupportedDocumentError("No safe extractor is registered.")
        return extractor
