"""Exclusive creation, bounded append, and atomic confirmed text replacement."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
from tempfile import TemporaryDirectory

from omega.core.exceptions import FileConflictError, FileWriteError
from omega.files.definitions import TEXT_EXTENSIONS
from omega.files.results import FileSnapshot, ValidatedFilePath


class TextFileWriter:
    """Modify only validated UTF-8 files within configured resource limits."""

    def __init__(
        self, maximum_write_size_bytes: int, maximum_resulting_file_size_bytes: int
    ) -> None:
        self.maximum_write_size_bytes = maximum_write_size_bytes
        self.maximum_resulting_file_size_bytes = maximum_resulting_file_size_bytes

    def create(self, target: ValidatedFilePath) -> None:
        """Create one empty UTF-8 file using exclusive creation semantics."""
        self._validate_extension(target.path)
        self._require_parent(target.path)
        try:
            with target.path.open("x", encoding="utf-8", newline=""):
                pass
        except FileExistsError as error:
            raise FileConflictError("The destination file already exists.") from error
        except OSError as error:
            raise FileWriteError("The file could not be created safely.") from error
        if not target.path.is_file() or target.path.is_symlink():
            raise FileWriteError("File creation could not be verified.")

    def write_empty(self, target: ValidatedFilePath, content: str) -> None:
        """Write to an existing empty regular file without replacement."""
        self._validate_content(content)
        self._validate_existing(target.path)
        if target.path.stat().st_size != 0:
            raise FileConflictError("The file already contains data.")
        try:
            with target.path.open("x", encoding="utf-8"):
                pass
        except FileExistsError:
            with target.path.open("w", encoding="utf-8", newline="") as stream:
                stream.write(content)
                stream.flush()
                os.fsync(stream.fileno())
        except OSError as error:
            raise FileWriteError("The file could not be written safely.") from error
        self._verify_text(target.path, content)

    def replace(
        self, target: ValidatedFilePath, content: str, expected: FileSnapshot
    ) -> None:
        """Atomically replace the exact file version approved by the user."""
        self._validate_content(content)
        self._validate_existing(target.path)
        if self.snapshot(target.path) != expected:
            raise FileConflictError(
                "The file changed after confirmation was requested."
            )
        try:
            with TemporaryDirectory(
                dir=target.path.parent, prefix=".omega-write-"
            ) as temporary:
                temporary_path = Path(temporary) / "replacement.tmp"
                with temporary_path.open("x", encoding="utf-8", newline="") as stream:
                    stream.write(content)
                    stream.flush()
                    os.fsync(stream.fileno())
                if temporary_path.stat().st_size != len(content.encode("utf-8")):
                    raise FileWriteError("The replacement file could not be verified.")
                os.replace(temporary_path, target.path)
        except FileConflictError:
            raise
        except OSError as error:
            raise FileWriteError("The file could not be replaced safely.") from error
        self._verify_text(target.path, content)

    def append(self, target: ValidatedFilePath, content: str) -> None:
        """Append exactly the supplied text without adding an implicit newline."""
        self._validate_content(content)
        self._validate_existing(target.path)
        initial_size = target.path.stat().st_size
        encoded_size = len(content.encode("utf-8"))
        if initial_size + encoded_size > self.maximum_resulting_file_size_bytes:
            raise FileWriteError("The resulting file would exceed the safe size limit.")
        try:
            with target.path.open("a", encoding="utf-8", newline="") as stream:
                stream.write(content)
                stream.flush()
                os.fsync(stream.fileno())
        except OSError as error:
            raise FileWriteError("The text could not be appended safely.") from error
        if target.path.stat().st_size != initial_size + encoded_size:
            raise FileWriteError("The append operation could not be verified.")

    @staticmethod
    def snapshot(path: Path) -> FileSnapshot:
        """Capture size, nanosecond timestamp, and SHA-256 for confirmation binding."""
        stat_result = path.stat()
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        return FileSnapshot(stat_result.st_size, stat_result.st_mtime_ns, digest)

    def _validate_content(self, content: str) -> None:
        if not isinstance(content, str):
            raise FileWriteError("Text content must be a string.")
        size = len(content.encode("utf-8"))
        if size > self.maximum_write_size_bytes:
            raise FileWriteError("The supplied text exceeds the safe write limit.")

    @staticmethod
    def _validate_extension(path: Path) -> None:
        if path.suffix.casefold() not in TEXT_EXTENSIONS:
            raise FileWriteError("That file type is not supported for text writing.")

    @classmethod
    def _validate_existing(cls, path: Path) -> None:
        cls._validate_extension(path)
        if not path.exists():
            raise FileWriteError("The requested file was not found.")
        if path.is_symlink() or not path.is_file():
            raise FileWriteError("The requested path is not a regular file.")

    @staticmethod
    def _require_parent(path: Path) -> None:
        if not path.parent.exists() or not path.parent.is_dir():
            raise FileWriteError("The destination folder does not exist.")

    @staticmethod
    def _verify_text(path: Path, expected: str) -> None:
        try:
            if path.read_text(encoding="utf-8") != expected:
                raise FileWriteError("The text write could not be verified.")
        except UnicodeError as error:
            raise FileWriteError("The text write could not be verified.") from error
