from dataclasses import replace
from pathlib import Path
from uuid import uuid4

from omega.folders import FolderOperationSettings
from tests.folder_support import build_folder_dispatcher


def test_listing_is_sorted_bounded_and_non_recursive(
    logical_roots: dict[str, Path],
) -> None:
    root = logical_roots["desktop"] / "Projects"
    root.mkdir()
    (root / "zeta.txt").write_text("z", encoding="utf-8")
    (root / "Alpha.txt").write_text("a", encoding="utf-8")
    (root / "Backend").mkdir()
    (root / "Backend" / "private.txt").write_text("x", encoding="utf-8")
    settings = replace(FolderOperationSettings(), maximum_listing_items=2)
    manager = build_folder_dispatcher(logical_roots, settings=settings).manager
    result = manager.list_folder("Projects", "desktop", uuid4())
    assert result.success
    assert result.data["folders"] == ["Backend"]
    assert result.data["files"] == ["Alpha.txt"]
    assert result.data["truncated"] is True
    assert "private.txt" not in result.user_message


def test_recursive_metadata_counts_bytes_and_reports_limits(
    logical_roots: dict[str, Path],
) -> None:
    root = logical_roots["desktop"] / "Projects"
    child = root / "Child"
    child.mkdir(parents=True)
    (root / "one.txt").write_bytes(b"123")
    (child / "two.txt").write_bytes(b"45")
    manager = build_folder_dispatcher(logical_roots).manager
    complete = manager.get_folder_information(
        "Projects", "desktop", uuid4(), recursive=True
    )
    assert complete.success
    assert complete.data["recursive_file_count"] == 2
    assert complete.data["recursive_folder_count"] == 1
    assert complete.data["total_bytes"] == 5
    limited_settings = replace(FolderOperationSettings(), maximum_scan_items=1)
    limited = build_folder_dispatcher(logical_roots, settings=limited_settings).manager
    partial = limited.get_folder_information(
        "Projects", "desktop", uuid4(), recursive=True
    )
    assert partial.success and partial.data["truncated"] is True
    assert "at least" in partial.user_message


def test_existence_distinguishes_files_from_folders(
    logical_roots: dict[str, Path],
) -> None:
    (logical_roots["desktop"] / "Projects").mkdir()
    (logical_roots["desktop"] / "notes").write_text("x", encoding="utf-8")
    manager = build_folder_dispatcher(logical_roots).manager
    assert manager.folder_exists("Projects", "desktop", uuid4()).data["exists"] is True
    assert manager.folder_exists("Missing", "desktop", uuid4()).data["exists"] is False
    assert manager.folder_exists("notes", "desktop", uuid4()).data["exists"] is False
