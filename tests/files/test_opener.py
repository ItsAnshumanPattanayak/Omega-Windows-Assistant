import sys
from pathlib import Path

import pytest

from omega.core.exceptions import FileOpenError, FilePathValidationError
from omega.files import FileLocationResolver, FilePathValidator, WindowsFileOpener


def _target(root: Path, name: str):  # type: ignore[no-untyped-def]
    location = FileLocationResolver({"documents": root}).resolve("documents")
    return FilePathValidator(protected_paths=()).require_file_path(location, name)


def test_opener_receives_only_validated_absolute_document_path(tmp_path: Path) -> None:
    document = tmp_path / "notes.txt"
    document.write_text("safe", encoding="utf-8")
    calls: list[str] = []
    WindowsFileOpener(lambda path: calls.append(path)).open(
        _target(tmp_path, "notes.txt")
    )
    assert calls == [str(document.resolve())]


@pytest.mark.parametrize(
    "name", ["program.exe", "script.ps1", "code.py", "code.js", "link.lnk"]
)
def test_opener_blocks_executable_and_script_extensions(
    tmp_path: Path, name: str
) -> None:
    path = tmp_path / name
    path.write_text("blocked", encoding="utf-8")
    with pytest.raises(FilePathValidationError):
        WindowsFileOpener(lambda value: None).open(_target(tmp_path, name))


def test_opener_reports_missing_failure_and_unsupported_platform(
    tmp_path: Path,
) -> None:
    with pytest.raises(FileOpenError, match="not found"):
        WindowsFileOpener(lambda value: None).open(_target(tmp_path, "missing.pdf"))
    document = tmp_path / "notes.txt"
    document.write_text("safe", encoding="utf-8")
    if sys.platform != "win32":
        with pytest.raises(FileOpenError, match="Windows"):
            WindowsFileOpener().open(_target(tmp_path, "notes.txt"))


def test_opener_wraps_windows_api_failure(tmp_path: Path) -> None:
    document = tmp_path / "notes.txt"
    document.write_text("safe", encoding="utf-8")

    def fail(path: str) -> None:
        raise OSError("failure")

    with pytest.raises(FileOpenError, match="could not"):
        WindowsFileOpener(fail).open(_target(tmp_path, "notes.txt"))
