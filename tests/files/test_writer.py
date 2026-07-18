from pathlib import Path

import pytest

from omega.core.exceptions import FileConflictError, FileWriteError
from omega.files import (
    FileLocationResolver,
    FilePathValidator,
    TextFileWriter,
)


def _target(root: Path, name: str):  # type: ignore[no-untyped-def]
    location = FileLocationResolver({"desktop": root}).resolve("desktop")
    return FilePathValidator(protected_paths=()).require_file_path(location, name)


def test_create_is_exclusive_utf8_and_requires_existing_parent(tmp_path: Path) -> None:
    writer = TextFileWriter(100, 200)
    target = _target(tmp_path, "author.txt")
    writer.create(target)
    assert target.path.read_bytes() == b""
    with pytest.raises(FileConflictError):
        writer.create(target)
    missing = _target(tmp_path, "missing/notes.txt")
    with pytest.raises(FileWriteError, match="folder"):
        writer.create(missing)


def test_atomic_replace_binds_snapshot_and_cleans_temporary_state(
    tmp_path: Path,
) -> None:
    path = tmp_path / "notes.txt"
    path.write_text("old", encoding="utf-8")
    target = _target(tmp_path, "notes.txt")
    writer = TextFileWriter(100, 200)
    snapshot = writer.snapshot(path)
    writer.replace(target, "new", snapshot)
    assert path.read_text(encoding="utf-8") == "new"
    assert not list(tmp_path.glob(".omega-write-*"))
    with pytest.raises(FileConflictError, match="changed"):
        writer.replace(target, "again", snapshot)


def test_append_is_exact_and_bounded(tmp_path: Path) -> None:
    path = tmp_path / "notes.txt"
    path.write_text("first", encoding="utf-8")
    target = _target(tmp_path, "notes.txt")
    writer = TextFileWriter(10, 10)
    writer.append(target, "line")
    assert path.read_text(encoding="utf-8") == "firstline"
    with pytest.raises(FileWriteError, match="resulting"):
        writer.append(target, "xx")
    with pytest.raises(FileWriteError, match="write limit"):
        TextFileWriter(1, 100).append(target, "xx")
