"""Strict bounded JSON import; content remains non-executable data."""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any
from uuid import UUID

from omega.productivity.configuration import ProductivityConfiguration
from omega.productivity.exceptions import ProductivityImportError
from omega.productivity.models import Note, ProductivityImportResult, Task, TaskList
from omega.productivity.service import ProductivityService


class ProductivityImportService:
    """Validate a versioned JSON document before any database mutation."""

    def __init__(
        self,
        configuration: ProductivityConfiguration,
        service: ProductivityService,
        import_root: Path,
    ) -> None:
        self.configuration = configuration
        self.service = service
        self.import_root = import_root.resolve(strict=False)

    def import_json(
        self, relative_name: str, *, preview: bool = False
    ) -> ProductivityImportResult:
        if not self.configuration.allow_json_import:
            raise ProductivityImportError("JSON import is disabled.")
        path = self._path(relative_name)
        try:
            size = path.stat().st_size
            if size > self.configuration.maximum_export_bytes:
                raise ProductivityImportError("The import exceeds its size limit.")
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as error:
            raise ProductivityImportError(
                "The productivity JSON file is invalid."
            ) from error
        notes, lists, tasks = self._validate(raw)
        if preview:
            return ProductivityImportResult(len(notes), len(lists), len(tasks), True)
        task_lists = [TaskList(item["name"], item["description"]) for item in lists]
        created_lists: dict[str, UUID] = {}
        for item, created in zip(lists, task_lists, strict=True):
            external_id = item.get("task_list_id")
            if isinstance(external_id, str):
                created_lists[external_id] = created.task_list_id
        note_records = [
            Note(item["title"], item["body"], tags=tuple(item["tags"]))
            for item in notes
        ]
        inbox: TaskList | None = None
        task_records: list[Task] = []
        for item in tasks:
            external_list_id = item.get("task_list_id")
            selected = (
                created_lists.get(external_list_id)
                if isinstance(external_list_id, str)
                else None
            )
            if selected is None:
                if inbox is None:
                    inbox = TaskList("Inbox")
                    task_lists.append(inbox)
                selected = inbox.task_list_id
            task_records.append(Task(selected, item["title"], item["description"]))
        self.service.repository.import_bundle(note_records, task_lists, task_records)
        return ProductivityImportResult(len(notes), len(lists), len(tasks), False)

    def _path(self, relative_name: str) -> Path:
        raw = Path(relative_name)
        if raw.is_absolute() or ".." in raw.parts or raw.suffix.casefold() != ".json":
            raise ProductivityImportError("Import must be a safe relative JSON path.")
        selected = (self.import_root / raw).resolve(strict=False)
        try:
            selected.relative_to(self.import_root)
        except ValueError as error:
            raise ProductivityImportError(
                "The import path leaves its approved location."
            ) from error
        return selected

    def _validate(
        self, raw: Any
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
        if not isinstance(raw, Mapping) or set(raw).difference(
            {"schema_version", "exported_at_utc", "notes", "task_lists", "tasks"}
        ):
            raise ProductivityImportError("The JSON import schema is invalid.")
        if raw.get("schema_version") != 1:
            raise ProductivityImportError("Unsupported productivity schema version.")
        notes = self._items(raw.get("notes", []), self.configuration.maximum_notes)
        lists = self._items(
            raw.get("task_lists", []), self.configuration.maximum_task_lists
        )
        tasks = self._items(raw.get("tasks", []), self.configuration.maximum_tasks)
        normalized_notes: list[dict[str, Any]] = []
        for item in notes:
            title = self._field(
                item,
                "title",
                self.configuration.maximum_note_title_characters,
                empty=True,
            )
            body = self._field(
                item,
                "body",
                self.configuration.maximum_note_body_characters,
                empty=True,
            )
            if not title.strip() and not body.strip():
                raise ProductivityImportError("Imported notes need a title or body.")
            normalized_notes.append(
                {"title": title, "body": body, "tags": self._tags(item.get("tags", []))}
            )
        normalized_lists = [
            {
                "task_list_id": item.get("task_list_id"),
                "name": self._field(item, "name", 200),
                "description": self._field(item, "description", 5_000, empty=True),
            }
            for item in lists
        ]
        normalized_tasks = [
            {
                "task_list_id": item.get("task_list_id"),
                "title": self._field(
                    item, "title", self.configuration.maximum_task_title_characters
                ),
                "description": self._field(
                    item,
                    "description",
                    self.configuration.maximum_task_description_characters,
                    empty=True,
                ),
            }
            for item in tasks
        ]
        return normalized_notes, normalized_lists, normalized_tasks

    @staticmethod
    def _items(value: Any, maximum: int) -> list[Mapping[str, Any]]:
        if not isinstance(value, list) or len(value) > maximum:
            raise ProductivityImportError("An imported item collection is invalid.")
        if not all(isinstance(item, Mapping) for item in value):
            raise ProductivityImportError("Imported items must be JSON objects.")
        return list(value)

    @staticmethod
    def _field(
        item: Mapping[str, Any], name: str, maximum: int, *, empty: bool = False
    ) -> str:
        value = item.get(name, "")
        if not isinstance(value, str) or len(value) > maximum:
            raise ProductivityImportError(f"Imported {name} is invalid.")
        if not empty and not value.strip():
            raise ProductivityImportError(f"Imported {name} is empty.")
        return value

    def _tags(self, value: Any) -> tuple[str, ...]:
        if (
            not isinstance(value, list)
            or len(value) > self.configuration.maximum_tags_per_item
            or not all(isinstance(item, str) for item in value)
        ):
            raise ProductivityImportError("Imported tags are invalid.")
        return tuple(value)
