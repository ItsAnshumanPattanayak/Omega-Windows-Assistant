from pathlib import Path
from uuid import uuid4

from omega.execution import FolderActionDispatcher


def test_create_one_folder_and_report_existing_conflicts(
    folder_dispatcher: FolderActionDispatcher, logical_roots: dict[str, Path]
) -> None:
    manager = folder_dispatcher.manager
    created = manager.create_folder("Projects", "desktop", uuid4())
    assert created.success and (logical_roots["desktop"] / "Projects").is_dir()
    existing = manager.create_folder("Projects", "desktop", uuid4())
    assert not existing.success and "already exists" in existing.user_message
    (logical_roots["desktop"] / "Conflict").write_text("file", encoding="utf-8")
    conflict = manager.create_folder("Conflict", "desktop", uuid4())
    assert not conflict.success and "file with that name" in conflict.user_message


def test_nested_creation_requires_existing_parent(
    folder_dispatcher: FolderActionDispatcher, logical_roots: dict[str, Path]
) -> None:
    manager = folder_dispatcher.manager
    missing = manager.create_folder(
        "Assignments", "documents", uuid4(), parent_path="College"
    )
    assert not missing.success
    assert not (logical_roots["documents"] / "College").exists()
    (logical_roots["documents"] / "College").mkdir()
    created = manager.create_folder(
        "Assignments", "documents", uuid4(), parent_path="College"
    )
    assert created.success
