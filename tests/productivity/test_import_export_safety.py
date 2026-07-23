import json
import subprocess
import sys
from pathlib import Path

import pytest

from omega.productivity import ExportFormat, ProductivityConfiguration
from omega.productivity.exceptions import (
    ProductivityConflictError,
    ProductivityExportError,
    ProductivityImportError,
)
from omega.productivity.export import ProductivityExportService
from omega.productivity.importers import ProductivityImportService
from omega.productivity.repositories import ProductivityRepository
from omega.productivity.service import ProductivityService


def test_import_has_no_side_effects(tmp_path: Path) -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import pathlib,threading;"
            "before=set(pathlib.Path('.').iterdir());"
            "import omega.productivity;"
            "assert before==set(pathlib.Path('.').iterdir());"
            "assert len(threading.enumerate())==1",
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )
    assert result.returncode == 0, result.stderr


def test_json_and_markdown_export_are_bounded_and_safe(
    tmp_path: Path,
    productivity: tuple[ProductivityService, ProductivityRepository],
) -> None:
    service, repository = productivity
    service.create_note("Code", "<script>alert(1)</script>")
    service.create_task("Do not execute: calc.exe")
    exporter = ProductivityExportService(
        ProductivityConfiguration(), repository, tmp_path
    )
    result = exporter.export("omega.json", ExportFormat.JSON)
    assert result.item_count == 2
    assert (
        json.loads((tmp_path / "omega.json").read_text(encoding="utf-8"))[
            "schema_version"
        ]
        == 1
    )
    markdown = exporter.export("omega.md", ExportFormat.MARKDOWN)
    assert markdown.bytes_written > 0
    assert "```text" in (tmp_path / "omega.md").read_text(encoding="utf-8")
    with pytest.raises(ProductivityExportError):
        exporter.export("../private.json", ExportFormat.JSON)


def test_json_import_preview_validates_format_and_content(
    tmp_path: Path,
    productivity: tuple[ProductivityService, ProductivityRepository],
) -> None:
    service, _repository = productivity
    payload = {
        "schema_version": 1,
        "notes": [
            {"title": "Imported", "body": "__import__('os').system('calc')", "tags": []}
        ],
        "task_lists": [{"task_list_id": "work", "name": "Work", "description": ""}],
        "tasks": [
            {
                "task_list_id": "work",
                "title": "Never execute this",
                "description": "powershell -Command calc",
            }
        ],
    }
    (tmp_path / "safe.json").write_text(json.dumps(payload), encoding="utf-8")
    importer = ProductivityImportService(ProductivityConfiguration(), service, tmp_path)
    preview = importer.import_json("safe.json", preview=True)
    assert preview.preview and preview.tasks_created == 1
    imported = importer.import_json("safe.json")
    assert imported.notes_created == 1
    with pytest.raises(ProductivityImportError):
        importer.import_json("../safe.json")
    (tmp_path / "bad.json").write_text('{"schema_version": 99}', encoding="utf-8")
    with pytest.raises(ProductivityImportError):
        importer.import_json("bad.json")


def test_import_conflict_rolls_back_entire_bundle(
    tmp_path: Path,
    productivity: tuple[ProductivityService, ProductivityRepository],
) -> None:
    service, repository = productivity
    payload = {
        "schema_version": 1,
        "notes": [{"title": "Must roll back", "body": "", "tags": []}],
        "task_lists": [
            {"name": "Duplicate", "description": ""},
            {"name": "duplicate", "description": ""},
        ],
        "tasks": [],
    }
    (tmp_path / "conflict.json").write_text(json.dumps(payload), encoding="utf-8")
    importer = ProductivityImportService(ProductivityConfiguration(), service, tmp_path)
    with pytest.raises(ProductivityConflictError):
        importer.import_json("conflict.json")
    assert repository.list_notes(include_archived=True) == ()
    assert repository.list_task_lists(include_archived=True) == ()
