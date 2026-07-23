"""Bounded UTF-8 JSON and plain-Markdown productivity export."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from omega.productivity.configuration import ProductivityConfiguration
from omega.productivity.enums import ExportFormat
from omega.productivity.exceptions import ProductivityExportError
from omega.productivity.models import ProductivityExportResult
from omega.productivity.repositories import ProductivityRepository


class ProductivityExportService:
    """Export inert records only inside an explicitly approved root."""

    def __init__(
        self,
        configuration: ProductivityConfiguration,
        repository: ProductivityRepository,
        export_root: Path,
    ) -> None:
        self.configuration = configuration
        self.repository = repository
        self.export_root = export_root.resolve(strict=False)

    def export(
        self,
        relative_name: str,
        format: ExportFormat,
        *,
        overwrite: bool = False,
    ) -> ProductivityExportResult:
        if format is ExportFormat.JSON and not self.configuration.allow_json_export:
            raise ProductivityExportError("JSON export is disabled.")
        if (
            format is ExportFormat.MARKDOWN
            and not self.configuration.allow_markdown_export
        ):
            raise ProductivityExportError("Markdown export is disabled.")
        path = self._path(relative_name, format)
        if path.exists() and not overwrite:
            raise ProductivityExportError("The export file already exists.")
        notes = self.repository.list_notes(include_archived=True, limit=200_000)
        lists = self.repository.list_task_lists(include_archived=True)
        tasks = self.repository.list_tasks(include_archived=True, limit=200_000)
        if format is ExportFormat.JSON:
            payload = {
                "schema_version": 1,
                "exported_at_utc": datetime.now(UTC).isoformat(),
                "notes": [item.to_dict() for item in notes],
                "task_lists": [item.to_dict() for item in lists],
                "tasks": [item.to_dict() for item in tasks],
            }
            content = (
                json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
            )
        else:
            content = self._markdown(notes, lists, tasks)
        encoded = content.encode("utf-8")
        if len(encoded) > self.configuration.maximum_export_bytes:
            raise ProductivityExportError("The export exceeds its configured limit.")
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            path.write_bytes(encoded)
        except OSError as error:
            raise ProductivityExportError("The export could not be written.") from error
        return ProductivityExportResult(
            str(path), format, len(notes) + len(tasks), len(encoded)
        )

    def _path(self, relative_name: str, format: ExportFormat) -> Path:
        raw = Path(relative_name)
        if raw.is_absolute() or ".." in raw.parts:
            raise ProductivityExportError("Export paths must be safe and relative.")
        expected = "." + format.value.replace("markdown", "md")
        if raw.suffix.casefold() != expected:
            raise ProductivityExportError(f"Export filename must end in {expected}.")
        selected = (self.export_root / raw).resolve(strict=False)
        try:
            selected.relative_to(self.export_root)
        except ValueError as error:
            raise ProductivityExportError(
                "The export path leaves its approved location."
            ) from error
        return selected

    @staticmethod
    def _markdown(
        notes: tuple[object, ...], lists: tuple[object, ...], tasks: tuple[object, ...]
    ) -> str:
        lines = [
            "# Omega Productivity Export",
            "",
            "Stored Markdown is inert text.",
            "",
        ]
        for note in notes:
            data = note.to_dict()  # type: ignore[attr-defined]
            lines.extend(
                [
                    f"## Note: {data['title']}",
                    "",
                    "```text",
                    str(data["body"]).replace("```", "` ` `"),
                    "```",
                    "",
                ]
            )
        list_names = {
            str(item.task_list_id): item.name  # type: ignore[attr-defined]
            for item in lists
        }
        lines.extend(["# Tasks", ""])
        for task in tasks:
            data = task.to_dict()  # type: ignore[attr-defined]
            mark = "x" if data["status"] == "completed" else " "
            lines.append(
                f"- [{mark}] {data['title']} "
                f"(list: {list_names.get(str(data['task_list_id']), 'Unknown')}; "
                f"priority: {data['priority']})"
            )
        return "\n".join(lines) + "\n"
