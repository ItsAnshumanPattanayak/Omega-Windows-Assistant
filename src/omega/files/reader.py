"""Bounded UTF-8 text reading with conservative binary and terminal safety."""

from __future__ import annotations

import re
from pathlib import Path

from omega.core.exceptions import FileReadError
from omega.files.definitions import TEXT_EXTENSIONS
from omega.files.results import TextReadResult, ValidatedFilePath

_ANSI_ESCAPE = re.compile(r"\x1b(?:\[[0-?]*[ -/]*[@-~]|\][^\x07]*(?:\x07|\x1b\\))")


class TextFileReader:
    """Read one validated regular text file without loading unbounded data."""

    def __init__(
        self, maximum_size_bytes: int, maximum_display_characters: int
    ) -> None:
        self.maximum_size_bytes = maximum_size_bytes
        self.maximum_display_characters = maximum_display_characters

    def read(self, target: ValidatedFilePath) -> TextReadResult:
        """Return sanitized UTF-8 text or a user-safe focused exception."""
        path = target.path
        self._validate_target(path)
        size = path.stat().st_size
        if size > self.maximum_size_bytes:
            raise FileReadError("That file is too large to display safely.")
        try:
            raw = path.read_bytes()
        except (OSError, PermissionError) as error:
            raise FileReadError("The file could not be read safely.") from error
        if b"\x00" in raw:
            raise FileReadError("That file appears to contain binary data.")
        try:
            content = raw.decode("utf-8-sig")
        except UnicodeDecodeError as error:
            raise FileReadError("That file is not valid UTF-8 text.") from error
        if self._has_excessive_controls(content):
            raise FileReadError("That file appears to contain binary data.")
        sanitized = self._sanitize(content)
        truncated = len(sanitized) > self.maximum_display_characters
        if truncated:
            sanitized = sanitized[: self.maximum_display_characters]
        return TextReadResult(sanitized, truncated, size)

    @staticmethod
    def _validate_target(path: Path) -> None:
        if path.suffix.casefold() not in TEXT_EXTENSIONS:
            raise FileReadError("That file type is not supported for text reading.")
        if not path.exists():
            raise FileReadError("The requested file was not found.")
        if path.is_symlink() or not path.is_file():
            raise FileReadError("The requested path is not a regular file.")

    @staticmethod
    def _has_excessive_controls(content: str) -> bool:
        if not content:
            return False
        controls = sum(
            character < " " and character not in "\n\r\t\b\f" for character in content
        )
        return controls > max(4, len(content) // 20)

    @staticmethod
    def _sanitize(content: str) -> str:
        without_ansi = _ANSI_ESCAPE.sub("", content)
        return "".join(
            (
                character
                if character in "\n\r\t" or character >= " " and character != "\x7f"
                else "�"
            )
            for character in without_ansi
        )
