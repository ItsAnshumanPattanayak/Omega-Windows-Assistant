"""Deterministic paragraph-aware bounded character chunking."""

from __future__ import annotations

import hashlib
from uuid import UUID, uuid5

from omega.knowledge.configuration import KnowledgeConfiguration
from omega.knowledge.exceptions import KnowledgeIndexError
from omega.knowledge.models import (
    DocumentExtractionResult,
    KnowledgeChunk,
)
from omega.models._serialization import JsonValue


class DeterministicChunker:
    def __init__(self, configuration: KnowledgeConfiguration) -> None:
        self.configuration = configuration

    def chunk(
        self, document_id: UUID, extraction: DocumentExtractionResult
    ) -> tuple[KnowledgeChunk, ...]:
        chunks: list[KnowledgeChunk] = []
        global_offset = 0
        for segment in extraction.segments:
            pieces = self._split(segment.text)
            local_search = 0
            for piece in pieces:
                local_start = segment.text.find(piece, local_search)
                if local_start < 0:
                    local_start = local_search
                start = global_offset + local_start
                end = start + len(piece)
                sequence = len(chunks)
                text_hash = hashlib.sha256(piece.encode("utf-8")).hexdigest()
                chunks.append(
                    KnowledgeChunk(
                        document_id,
                        sequence,
                        piece,
                        text_hash,
                        start,
                        end,
                        chunk_id=uuid5(document_id, f"{sequence}:{text_hash}"),
                        page_number=segment.page_number,
                        section_title=segment.section_title,
                        metadata=self._location_metadata(
                            segment.line_start,
                            segment.line_end,
                            segment.text,
                            local_start,
                            piece,
                        ),
                    )
                )
                local_search = max(
                    local_start
                    + len(piece)
                    - self.configuration.chunk_overlap_characters,
                    local_start + 1,
                )
                if len(chunks) > self.configuration.maximum_chunks_per_document:
                    raise KnowledgeIndexError("The document requires too many chunks.")
            global_offset += len(segment.text) + 2
        if not chunks:
            raise KnowledgeIndexError("No non-empty chunks could be created.")
        return tuple(chunks)

    @staticmethod
    def _location_metadata(
        segment_start: int | None,
        segment_end: int | None,
        segment_text: str,
        local_start: int,
        piece: str,
    ) -> dict[str, JsonValue]:
        if segment_start is None or segment_end is None:
            return {}
        line_start = segment_start + segment_text[:local_start].count("\n")
        line_end = min(segment_end, line_start + piece.count("\n"))
        return {"line_start": line_start, "line_end": line_end}

    def _split(self, text: str) -> tuple[str, ...]:
        size = self.configuration.chunk_size_characters
        overlap = self.configuration.chunk_overlap_characters
        if len(text) <= size:
            return (text.strip(),)
        chunks: list[str] = []
        start = 0
        while start < len(text):
            tentative = min(start + size, len(text))
            end = tentative
            if tentative < len(text):
                paragraph = text.rfind("\n\n", start + size // 2, tentative)
                space = text.rfind(" ", start + size // 2, tentative)
                end = max(paragraph + 2 if paragraph >= 0 else -1, space)
                if end <= start:
                    end = tentative
            value = text[start:end].strip()
            if value:
                chunks.append(value)
            if end >= len(text):
                break
            start = max(end - overlap, start + 1)
            while start < end and not text[start - 1].isspace():
                start += 1
        return tuple(chunks)
