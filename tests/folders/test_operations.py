from dataclasses import replace
from pathlib import Path
from uuid import uuid4

import pytest

from omega.core.exceptions import FolderOperationError
from omega.folders import FolderOperationSettings
from tests.folder_support import build_folder_dispatcher


def _tree(root: Path) -> None:
    (root / "Backend").mkdir(parents=True)
    (root / "README.md").write_text("readme", encoding="utf-8")
    (root / "Backend" / "app.py").write_text("pass", encoding="utf-8")


def test_rename_copy_and_same_volume_move_preserve_tree(
    logical_roots: dict[str, Path],
) -> None:
    source = logical_roots["desktop"] / "Projects"
    _tree(source)
    manager = build_folder_dispatcher(logical_roots).manager
    renamed = manager.rename_folder("Projects", "Omega Projects", "desktop", uuid4())
    assert renamed.success and not source.exists()
    renamed_source = logical_roots["desktop"] / "Omega Projects"
    copied = manager.copy_folder("Omega Projects", "desktop", "documents", uuid4())
    assert copied.success and renamed_source.exists()
    copied_path = logical_roots["documents"] / "Omega Projects"
    assert (copied_path / "Backend" / "app.py").read_text(encoding="utf-8") == "pass"
    moved = manager.move_folder("Omega Projects", "documents", "downloads", uuid4())
    assert moved.success and not copied_path.exists()
    assert (logical_roots["downloads"] / "Omega Projects" / "README.md").is_file()


def test_destination_conflict_never_merges_or_replaces(
    logical_roots: dict[str, Path],
) -> None:
    source = logical_roots["desktop"] / "Projects"
    _tree(source)
    destination = logical_roots["documents"] / "Projects"
    destination.mkdir()
    marker = destination / "existing.txt"
    marker.write_text("keep", encoding="utf-8")
    manager = build_folder_dispatcher(logical_roots).manager
    result = manager.copy_folder("Projects", "desktop", "documents", uuid4())
    assert not result.success
    assert marker.read_text(encoding="utf-8") == "keep"
    assert not (destination / "README.md").exists()


def test_copy_preflight_rejects_limits_and_destination_inside_source(
    logical_roots: dict[str, Path],
) -> None:
    source = logical_roots["desktop"] / "Projects"
    _tree(source)
    settings = replace(FolderOperationSettings(), maximum_copy_items=1)
    manager = build_folder_dispatcher(logical_roots, settings=settings).manager
    limited = manager.copy_folder("Projects", "desktop", "documents", uuid4())
    assert not limited.success and "too large" in limited.user_message
    nested_destination = manager._resolve("desktop", "Projects/Nested")
    validated_source = manager._resolve("desktop", "Projects", require_existing=True)
    try:
        manager.operations.preflight(
            validated_source,
            nested_destination,
            maximum_depth=20,
            maximum_items=100,
            maximum_bytes=1000,
        )
    except Exception as error:
        assert "inside itself" in str(error)
    else:
        raise AssertionError("Preflight accepted a destination inside the source.")


def test_cross_volume_move_is_blocked_without_touching_source(
    logical_roots: dict[str, Path], monkeypatch
) -> None:
    source = logical_roots["desktop"] / "Projects"
    _tree(source)
    manager = build_folder_dispatcher(logical_roots).manager
    monkeypatch.setattr(
        manager.operations, "_same_volume", lambda source, parent: False
    )
    result = manager.move_folder("Projects", "desktop", "documents", uuid4())
    assert not result.success and "different drive" in result.user_message
    assert source.is_dir() and not (logical_roots["documents"] / "Projects").exists()


def test_nested_symlink_is_rejected_before_destination_creation(
    logical_roots: dict[str, Path], tmp_path: Path
) -> None:
    source = logical_roots["desktop"] / "Projects"
    source.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    try:
        (source / "linked").symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip("Directory symlink creation is unavailable on this host.")
    manager = build_folder_dispatcher(logical_roots).manager
    result = manager.copy_folder("Projects", "desktop", "documents", uuid4())
    assert not result.success
    assert not (logical_roots["documents"] / "Projects").exists()


def test_case_only_rename_preserves_contents(logical_roots: dict[str, Path]) -> None:
    source = logical_roots["desktop"] / "Projects"
    source.mkdir()
    (source / "data.txt").write_text("keep", encoding="utf-8")
    manager = build_folder_dispatcher(logical_roots).manager
    result = manager.rename_folder("Projects", "PROJECTS", "desktop", uuid4())
    assert result.success
    assert (logical_roots["desktop"] / "PROJECTS" / "data.txt").read_text(
        encoding="utf-8"
    ) == "keep"


def test_failed_copy_cleans_only_private_staging_tree(
    logical_roots: dict[str, Path], monkeypatch
) -> None:
    source = logical_roots["desktop"] / "Projects"
    _tree(source)
    manager = build_folder_dispatcher(logical_roots).manager

    def fail_after_partial(source_path: Path, staging: Path) -> None:
        (staging / "partial.txt").write_text("partial", encoding="utf-8")
        raise FolderOperationError("simulated copy failure")

    monkeypatch.setattr(manager.operations, "_copy_contents", fail_after_partial)
    result = manager.copy_folder("Projects", "desktop", "documents", uuid4())
    assert not result.success
    assert not (logical_roots["documents"] / "Projects").exists()
    assert list(logical_roots["documents"].iterdir()) == []
    assert source.is_dir()


def test_move_verification_failure_restores_source(
    logical_roots: dict[str, Path], monkeypatch
) -> None:
    source = logical_roots["desktop"] / "Projects"
    _tree(source)
    manager = build_folder_dispatcher(logical_roots).manager

    def reject_verification(expected, actual) -> None:
        raise FolderOperationError("simulated verification failure")

    monkeypatch.setattr(manager.operations, "_require_equivalent", reject_verification)
    result = manager.move_folder("Projects", "desktop", "documents", uuid4())
    assert not result.success
    assert source.is_dir()
    assert not (logical_roots["documents"] / "Projects").exists()
