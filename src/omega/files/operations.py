"""Conflict-safe regular-file rename, copy, move, and metadata inspection."""

from __future__ import annotations

import hashlib
import os
import shutil
import stat
from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4

from omega.core.exceptions import FileConflictError, FileOperationError
from omega.files.results import FileMetadata, ValidatedFilePath


class FileOperationsService:
    """Perform one validated file operation and verify its postconditions."""

    def exists(self, target: ValidatedFilePath) -> bool:
        """Report only regular non-symlink file existence."""
        return (
            target.path.exists()
            and target.path.is_file()
            and not target.path.is_symlink()
        )

    def metadata(self, target: ValidatedFilePath) -> FileMetadata:
        """Return safe basic metadata without exposing the absolute path."""
        self._require_regular(target.path)
        details = target.path.stat()
        return FileMetadata(
            name=target.path.name,
            logical_location=target.location.logical_name,
            relative_path=target.relative_path.as_posix(),
            size_bytes=details.st_size,
            created_at=datetime.fromtimestamp(details.st_ctime, UTC),
            modified_at=datetime.fromtimestamp(details.st_mtime, UTC),
            extension=target.path.suffix.casefold(),
            read_only=not bool(details.st_mode & stat.S_IWRITE),
        )

    def rename(self, source: ValidatedFilePath, destination: ValidatedFilePath) -> None:
        """Rename inside one directory without replacing a destination."""
        self._require_regular(source.path)
        if source.path.parent.resolve() != destination.path.parent.resolve():
            raise FileOperationError("Rename cannot move a file to another folder.")
        if source.path == destination.path:
            raise FileConflictError("The source and destination names are the same.")
        if destination.path.exists():
            same_casefold = (
                source.path.name.casefold() == destination.path.name.casefold()
            )
            if not same_casefold:
                raise FileConflictError("The destination file already exists.")
        case_only = source.path.name.casefold() == destination.path.name.casefold()
        try:
            if case_only:
                temporary = source.path.with_name(f".omega-rename-{uuid4().hex}.tmp")
                os.rename(source.path, temporary)
                try:
                    os.rename(temporary, destination.path)
                except OSError:
                    os.rename(temporary, source.path)
                    raise
            else:
                os.rename(source.path, destination.path)
        except OSError as error:
            raise FileOperationError("The file could not be renamed safely.") from error
        if source.path.exists() or not destination.path.is_file():
            raise FileOperationError("The rename operation could not be verified.")

    def copy(self, source: ValidatedFilePath, destination: ValidatedFilePath) -> None:
        """Copy through a private temporary directory and never overwrite."""
        self._require_regular(source.path)
        self._require_destination(destination.path)
        source_hash = self._hash(source.path)
        try:
            with TemporaryDirectory(
                dir=destination.path.parent, prefix=".omega-copy-"
            ) as temporary:
                temporary_path = Path(temporary) / destination.path.name
                shutil.copyfile(source.path, temporary_path, follow_symlinks=False)
                if temporary_path.stat().st_size != source.path.stat().st_size:
                    raise FileOperationError(
                        "The copied file size could not be verified."
                    )
                if self._hash(temporary_path) != source_hash:
                    raise FileOperationError(
                        "The copied file contents could not be verified."
                    )
                os.rename(temporary_path, destination.path)
        except FileOperationError:
            raise
        except FileExistsError as error:
            raise FileConflictError("The destination file already exists.") from error
        except OSError as error:
            raise FileOperationError("The file could not be copied safely.") from error
        if (
            not destination.path.is_file()
            or self._hash(destination.path) != source_hash
        ):
            raise FileOperationError("The copy operation could not be verified.")

    def move(self, source: ValidatedFilePath, destination: ValidatedFilePath) -> None:
        """Move one regular file without replacement and verify both endpoints."""
        self._require_regular(source.path)
        self._require_destination(destination.path)
        size = source.path.stat().st_size
        digest = self._hash(source.path)
        try:
            shutil.move(str(source.path), str(destination.path))
        except shutil.Error as error:
            raise FileConflictError("The destination file already exists.") from error
        except OSError as error:
            raise FileOperationError("The file could not be moved safely.") from error
        if source.path.exists():
            raise FileOperationError("The source remained after the move.")
        if not destination.path.is_file():
            raise FileOperationError("The move destination could not be verified.")
        if (
            destination.path.stat().st_size != size
            or self._hash(destination.path) != digest
        ):
            raise FileOperationError("The moved file contents could not be verified.")

    @staticmethod
    def _require_regular(path: Path) -> None:
        if not path.exists():
            raise FileOperationError("The source file was not found.")
        if path.is_symlink() or not path.is_file():
            raise FileOperationError("The source must be a regular file.")

    @staticmethod
    def _require_destination(path: Path) -> None:
        if not path.parent.exists() or not path.parent.is_dir():
            raise FileOperationError("The destination folder does not exist.")
        if path.exists():
            raise FileConflictError("The destination file already exists.")

    @staticmethod
    def _hash(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for block in iter(lambda: stream.read(65_536), b""):
                digest.update(block)
        return digest.hexdigest()
