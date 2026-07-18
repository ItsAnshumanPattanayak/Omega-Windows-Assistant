from dataclasses import replace
from pathlib import Path
from uuid import uuid4

from omega.folders import FolderOperationSettings
from tests.folder_support import build_folder_dispatcher


def test_exact_case_insensitive_bounded_folder_search(
    logical_roots: dict[str, Path],
) -> None:
    (logical_roots["documents"] / "College" / "Notes").mkdir(parents=True)
    (logical_roots["documents"] / "Archive" / "notes").mkdir(parents=True)
    (logical_roots["documents"] / "Noteworthy").mkdir()
    manager = build_folder_dispatcher(logical_roots).manager
    result = manager.search_folders("NOTES", "documents", uuid4())
    assert result.success
    assert [match["relative_path"] for match in result.data["matches"]] == [
        "Archive/notes",
        "College/Notes",
    ]
    assert "Noteworthy" not in result.user_message


def test_search_skips_links_and_obeys_depth(
    logical_roots: dict[str, Path], tmp_path: Path
) -> None:
    deep = logical_roots["documents"] / "one" / "two" / "Target"
    deep.mkdir(parents=True)
    manager = build_folder_dispatcher(logical_roots).manager
    manager.settings = type(manager.settings)(search_max_depth=1)
    result = manager.search_folders("Target", "documents", uuid4())
    assert result.data["matches"] == []


def test_search_result_limit_reports_truncation(
    logical_roots: dict[str, Path],
) -> None:
    for parent in ("one", "two", "three"):
        (logical_roots["documents"] / parent / "Target").mkdir(parents=True)
    settings = replace(FolderOperationSettings(), search_max_results=2)
    manager = build_folder_dispatcher(logical_roots, settings=settings).manager
    result = manager.search_folders("Target", "documents", uuid4())
    assert len(result.data["matches"]) == 2
    assert result.data["truncated"] is True
    assert "Showing the first 2" in result.user_message
