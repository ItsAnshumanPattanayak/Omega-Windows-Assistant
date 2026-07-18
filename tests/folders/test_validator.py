from pathlib import Path

import pytest

from omega.core.exceptions import FolderValidationError
from omega.files.results import ResolvedLocation
from omega.folders import FolderPathValidator, WindowsFolderNameValidator


@pytest.mark.parametrize("name", ["Projects", "College Work", "資料", "notes.backup"])
def test_valid_folder_names(name: str) -> None:
    assert WindowsFolderNameValidator.validate_component(name) == name


@pytest.mark.parametrize(
    "name",
    [
        "",
        "   ",
        "bad<name",
        "trailing.",
        "trailing ",
        "CON",
        "con.folder",
        "NUL.backup",
        "COM1.data",
        ".",
        "..",
        "bad:name",
        "a/b",
        "a\\b",
        "bad\x01name",
        "x" * 241,
    ],
)
def test_invalid_folder_names_are_rejected(name: str) -> None:
    with pytest.raises(FolderValidationError):
        WindowsFolderNameValidator.validate_component(name)


@pytest.mark.parametrize(
    "value",
    [
        "../escape",
        r"C:\Windows",
        r"\\server\share",
        r"\\?\C:\Temp",
        "~\\Temp",
        "%TEMP%",
    ],
)
def test_unsafe_relative_paths_are_rejected(tmp_path: Path, value: str) -> None:
    location = ResolvedLocation("desktop", "Desktop", tmp_path)
    with pytest.raises(FolderValidationError):
        FolderPathValidator(protected_paths=()).require_folder_path(location, value)


def test_safe_nested_path_and_protected_real_path(tmp_path: Path) -> None:
    protected = tmp_path / "actual-protected"
    protected.mkdir()
    location = ResolvedLocation("desktop", "Desktop", tmp_path)
    validator = FolderPathValidator((protected,))
    safe = validator.require_folder_path(location, "College/Assignments")
    assert safe.path == tmp_path / "College" / "Assignments"
    with pytest.raises(FolderValidationError):
        validator.require_folder_path(location, "actual-protected")


def test_symlink_escape_is_rejected_when_supported(tmp_path: Path) -> None:
    outside = tmp_path.parent / f"{tmp_path.name}-outside"
    outside.mkdir(exist_ok=True)
    link = tmp_path / "link"
    try:
        link.symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip("Directory symlink creation is unavailable on this host.")
    location = ResolvedLocation("desktop", "Desktop", tmp_path)
    with pytest.raises(FolderValidationError):
        FolderPathValidator(protected_paths=()).require_folder_path(
            location, "link/child"
        )
