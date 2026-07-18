import pytest

from omega.core.exceptions import FilePathValidationError
from omega.files import WindowsFilenameValidator


@pytest.mark.parametrize("name", ["notes.txt", "My Notes.md", "résumé.csv"])
def test_valid_windows_filenames(name: str) -> None:
    assert WindowsFilenameValidator.validate_component(name) == name


@pytest.mark.parametrize(
    "name",
    [
        "",
        "   ",
        "bad?.txt",
        "bad<name>.txt",
        "trailing.",
        "trailing ",
        "CON",
        "nul.json",
        "COM1.md",
        "LPT9.txt",
        "x" * 241,
    ],
)
def test_invalid_and_reserved_windows_filenames(name: str) -> None:
    with pytest.raises(FilePathValidationError):
        WindowsFilenameValidator.validate_component(name)


@pytest.mark.parametrize(
    "name", ["virus.bat", "setup.exe", "script.ps1", "safe.txt.exe"]
)
def test_executable_or_script_extensions_are_blocked(name: str) -> None:
    with pytest.raises(FilePathValidationError):
        WindowsFilenameValidator.normalize_text_filename(name)


def test_extension_inference_conflict_and_no_double_append() -> None:
    assert (
        WindowsFilenameValidator.normalize_text_filename("author", ".txt")
        == "author.txt"
    )
    assert (
        WindowsFilenameValidator.normalize_text_filename("author.txt", ".txt")
        == "author.txt"
    )
    with pytest.raises(FilePathValidationError, match="conflicts"):
        WindowsFilenameValidator.normalize_text_filename("data.json", ".txt")
