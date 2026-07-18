import os
from pathlib import Path

import pytest

from omega.core.exceptions import FilePathValidationError
from omega.files import FileLocationResolver, FilePathValidator, SafeFilePathResolver


def _resolver(root: Path, *, protected: tuple[Path, ...] = ()) -> SafeFilePathResolver:
    return SafeFilePathResolver(
        FileLocationResolver({"desktop": root}),
        FilePathValidator(protected_paths=protected),
    )


def test_safe_child_and_existing_nested_parent(tmp_path: Path) -> None:
    nested = tmp_path / "College"
    nested.mkdir()
    result = _resolver(tmp_path).resolve("desktop", "College/notes.txt")
    assert result.path == nested / "notes.txt"
    assert result.relative_path == Path("College", "notes.txt")


@pytest.mark.parametrize(
    "value",
    [
        "../notes.txt",
        "College/../notes.txt",
        r"C:\Windows\notes.txt",
        r"C:notes.txt",
        r"\\server\share\notes.txt",
        r"\\?\C:\notes.txt",
        "notes.txt:secret",
        "%USERPROFILE%/notes.txt",
        "~/notes.txt",
    ],
)
def test_traversal_absolute_unc_device_ads_and_expansion_are_rejected(
    tmp_path: Path, value: str
) -> None:
    with pytest.raises(FilePathValidationError):
        _resolver(tmp_path).resolve("desktop", value)


def test_protected_target_and_directory_as_file_are_rejected(tmp_path: Path) -> None:
    protected = tmp_path / ".git"
    protected.mkdir()
    with pytest.raises(FilePathValidationError, match="protected"):
        _resolver(tmp_path, protected=(protected,)).resolve(
            "desktop", ".git/config.txt"
        )
    directory = tmp_path / "notes.txt"
    directory.mkdir()
    with pytest.raises(FilePathValidationError, match="directory"):
        _resolver(tmp_path).resolve("desktop", "notes.txt")


def test_symlink_escape_is_rejected_when_supported(tmp_path: Path) -> None:
    root = tmp_path / "root"
    outside = tmp_path / "outside"
    root.mkdir()
    outside.mkdir()
    link = root / "linked"
    try:
        os.symlink(outside, link, target_is_directory=True)
    except OSError:
        pytest.skip("Creating a directory symlink is not permitted on this host.")
    with pytest.raises(FilePathValidationError, match="approved location"):
        _resolver(root).resolve("desktop", "linked/notes.txt")


def test_structured_validation_outcome(tmp_path: Path) -> None:
    location = FileLocationResolver({"desktop": tmp_path}).resolve("desktop")
    validator = FilePathValidator(protected_paths=())
    valid = validator.validate(location, "notes.txt")
    invalid = validator.validate(location, "../notes.txt")
    assert valid.valid and valid.validated_path is not None
    assert not invalid.valid and invalid.code == "INVALID_FILE_PATH"
