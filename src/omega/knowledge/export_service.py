"""Safe bounded exports of metadata, search hits, and grounded answers."""

from __future__ import annotations

import json
import os
from pathlib import Path, PureWindowsPath

from omega.knowledge.configuration import KnowledgeConfiguration
from omega.knowledge.enums import KnowledgeExportFormat
from omega.knowledge.exceptions import KnowledgeError
from omega.knowledge.models import (
    KnowledgeAnswer,
    KnowledgeExportResult,
    KnowledgeSearchResult,
)
from omega.knowledge.repositories import KnowledgeRepository


class KnowledgeExportService:
    def __init__(
        self,
        configuration: KnowledgeConfiguration,
        repository: KnowledgeRepository,
        export_root: Path,
    ) -> None:
        self.configuration = configuration
        self.repository = repository
        self.export_root = export_root.resolve(strict=False)

    def export_metadata(
        self,
        filename: str,
        format: KnowledgeExportFormat,
        *,
        search: KnowledgeSearchResult | None = None,
        answer: KnowledgeAnswer | None = None,
        overwrite: bool = False,
    ) -> KnowledgeExportResult:
        path = self._path(filename, format)
        collections = self.repository.list_collections(include_archived=True)
        documents = self.repository.list_documents(include_archived=True, limit=10_000)
        payload = {
            "schema_version": 1,
            "collections": [item.to_dict() for item in collections],
            "documents": [item.to_dict() for item in documents],
            "search": self._search(search),
            "answer": self._answer(answer),
        }
        if format is KnowledgeExportFormat.JSON:
            content = (
                json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
            )
        else:
            lines = [
                "# Omega local knowledge export",
                "",
                "No source paths or vectors.",
            ]
            for item in documents:
                lines.extend(
                    (
                        "",
                        f"## {item.title}",
                        f"- ID: `{item.document_id}`",
                        f"- Type: {item.source_type.value}",
                        f"- Status: {item.status.value}",
                    )
                )
            if answer is not None:
                lines.extend(("", "## Grounded answer", "", answer.answer))
                lines.extend(f"- {source.label()}" for source in answer.sources)
            content = "\n".join(lines) + "\n"
        encoded = content.encode("utf-8")
        if len(encoded) > self.configuration.maximum_file_bytes:
            raise KnowledgeError("The knowledge export exceeds the configured limit.")
        self.export_root.mkdir(parents=True, exist_ok=True)
        mode = "wb" if overwrite else "xb"
        try:
            with path.open(mode) as stream:
                stream.write(encoded)
        except FileExistsError as error:
            raise KnowledgeError("The export already exists.") from error
        return KnowledgeExportResult(str(path), format, len(documents), len(encoded))

    def _path(self, filename: str, format: KnowledgeExportFormat) -> Path:
        windows = PureWindowsPath(filename)
        if (
            windows.is_absolute()
            or windows.drive
            or windows.root
            or any(part in {"", ".", ".."} for part in windows.parts)
        ):
            raise KnowledgeError("Knowledge exports require a safe relative filename.")
        expected = ".json" if format is KnowledgeExportFormat.JSON else ".md"
        if Path(filename).suffix.casefold() != expected:
            raise KnowledgeError(f"The export filename must end with {expected}.")
        path = self.export_root.joinpath(*windows.parts).resolve(strict=False)
        try:
            contained = os.path.commonpath((path, self.export_root)) == str(
                self.export_root
            )
        except ValueError:
            contained = False
        if not contained:
            raise KnowledgeError("The export path leaves its approved directory.")
        return path

    @staticmethod
    def _search(value: KnowledgeSearchResult | None) -> object:
        if value is None:
            return None
        return {
            "query": value.query.text,
            "hits": [
                {
                    "score": hit.score,
                    "source": hit.source.label(),
                    "preview": hit.source.preview,
                }
                for hit in value.hits
            ],
        }

    @staticmethod
    def _answer(value: KnowledgeAnswer | None) -> object:
        if value is None:
            return None
        return {
            "question": value.question,
            "answer": value.answer,
            "supported": value.supported,
            "sources": [source.label() for source in value.sources],
        }
