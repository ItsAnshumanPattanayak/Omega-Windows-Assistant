from pathlib import Path

import pytest

from omega.core.exceptions import FileReadError
from omega.files import FileLocationResolver, FilePathValidator, TextFileReader


def _target(root: Path, name: str):  # type: ignore[no-untyped-def]
    location = FileLocationResolver({"desktop": root}).resolve("desktop")
    return FilePathValidator(protected_paths=()).require_file_path(location, name)


def test_reads_utf8_bom_empty_and_sanitizes_terminal_controls(tmp_path: Path) -> None:
    path = tmp_path / "notes.txt"
    path.write_bytes(b"\xef\xbb\xbfHello\x1b[31m world\x1b[0m")
    result = TextFileReader(100, 100).read(_target(tmp_path, "notes.txt"))
    assert result.content == "Hello world"
    assert not result.truncated
    path.write_text("", encoding="utf-8")
    assert TextFileReader(100, 100).read(_target(tmp_path, "notes.txt")).content == ""


def test_read_size_binary_decode_extension_and_display_limits(tmp_path: Path) -> None:
    path = tmp_path / "notes.txt"
    path.write_text("abcdefgh", encoding="utf-8")
    assert TextFileReader(8, 4).read(_target(tmp_path, "notes.txt")).content == "abcd"
    with pytest.raises(FileReadError, match="too large"):
        TextFileReader(7, 10).read(_target(tmp_path, "notes.txt"))
    path.write_bytes(b"text\x00binary")
    with pytest.raises(FileReadError, match="binary"):
        TextFileReader(20, 20).read(_target(tmp_path, "notes.txt"))
    path.write_bytes(b"\xff\xfe")
    with pytest.raises(FileReadError, match="UTF-8"):
        TextFileReader(20, 20).read(_target(tmp_path, "notes.txt"))
    binary = tmp_path / "image.png"
    binary.write_bytes(b"image")
    with pytest.raises(FileReadError, match="file type"):
        TextFileReader(20, 20).read(_target(tmp_path, "image.png"))
