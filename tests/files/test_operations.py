from pathlib import Path

import pytest

from omega.core.exceptions import FileConflictError, FileOperationError
from omega.files import FileLocationResolver, FileOperationsService, FilePathValidator


def _target(root: Path, location_name: str, name: str):  # type: ignore[no-untyped-def]
    location = FileLocationResolver({location_name: root}).resolve(location_name)
    return FilePathValidator(protected_paths=()).require_file_path(location, name)


def test_metadata_existence_and_rename_without_overwrite(tmp_path: Path) -> None:
    source_path = tmp_path / "author.txt"
    source_path.write_text("Anshuman", encoding="utf-8")
    source = _target(tmp_path, "desktop", "author.txt")
    destination = _target(tmp_path, "desktop", "writer.txt")
    operations = FileOperationsService()
    assert operations.exists(source)
    metadata = operations.metadata(source)
    assert metadata.size_bytes == len("Anshuman")
    assert "tmp" not in metadata.relative_path
    operations.rename(source, destination)
    assert destination.path.read_text(encoding="utf-8") == "Anshuman"
    conflict = _target(tmp_path, "desktop", "conflict.txt")
    conflict.path.write_text("existing", encoding="utf-8")
    with pytest.raises(FileConflictError):
        operations.rename(destination, conflict)


def test_copy_and_move_verify_contents_and_refuse_conflicts(tmp_path: Path) -> None:
    source_root = tmp_path / "source"
    destination_root = tmp_path / "destination"
    source_root.mkdir()
    destination_root.mkdir()
    (source_root / "notes.txt").write_text("content", encoding="utf-8")
    source = _target(source_root, "desktop", "notes.txt")
    copied = _target(destination_root, "documents", "notes.txt")
    operations = FileOperationsService()
    operations.copy(source, copied)
    assert source.path.exists() and copied.path.read_text(encoding="utf-8") == "content"
    with pytest.raises(FileConflictError):
        operations.copy(source, copied)
    moved = _target(destination_root, "documents", "moved.txt")
    operations.move(source, moved)
    assert (
        not source.path.exists() and moved.path.read_text(encoding="utf-8") == "content"
    )
    directory = source_root / "folder.txt"
    directory.mkdir()
    location = FileLocationResolver({"desktop": source_root}).resolve("desktop")
    directory_target = FilePathValidator(protected_paths=()).require_file_path(
        location, "folder.txt", expect_file=False
    )
    with pytest.raises(FileOperationError, match="regular"):
        operations.copy(directory_target, copied)
