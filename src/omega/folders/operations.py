"""Preflighted folder rename, recursive copy, and same-volume move."""

from __future__ import annotations

import os
import shutil
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4

from omega.core.exceptions import (
    FolderConflictError,
    FolderCrossVolumeMoveError,
    FolderOperationError,
    FolderValidationError,
)
from omega.folders.inspector import FolderInspector
from omega.folders.results import FolderTreeSnapshot, ValidatedFolderPath
from omega.folders.validator import FolderPathValidator, is_link_or_reparse


class FolderOperations:
    """Execute directory-tree operations only after bounded read-only preflight."""

    def __init__(
        self, inspector: FolderInspector, validator: FolderPathValidator
    ) -> None:
        self.inspector = inspector
        self.validator = validator

    def preflight(
        self,
        source: ValidatedFolderPath,
        destination: ValidatedFolderPath,
        *,
        maximum_depth: int,
        maximum_items: int,
        maximum_bytes: int,
    ) -> FolderTreeSnapshot:
        self._require_source(source)
        self._require_destination(destination)
        source_resolved = source.path.resolve()
        destination_resolved = destination.path.resolve(strict=False)
        if self._same_path(source_resolved, destination_resolved):
            raise FolderConflictError("The source and destination are the same folder.")
        if self._contained(destination_resolved, source_resolved):
            raise FolderValidationError(
                "A folder cannot be copied or moved inside itself."
            )
        if self._contained(source_resolved, destination_resolved):
            raise FolderValidationError(
                "The source cannot contain its destination parent."
            )
        return self.inspector.scan_tree(
            source,
            maximum_depth=maximum_depth,
            maximum_items=maximum_items,
            maximum_bytes=maximum_bytes,
            strict_limits=True,
            reject_inaccessible=True,
        )

    def rename(
        self, source: ValidatedFolderPath, destination: ValidatedFolderPath
    ) -> None:
        self._require_source(source)
        if source.path.parent.resolve() != destination.path.parent.resolve():
            raise FolderOperationError("Rename must keep the same parent folder.")
        if (
            source.path.parent.resolve() == destination.path.parent.resolve()
            and source.path.name == destination.path.name
        ):
            raise FolderConflictError("The source and destination names are the same.")
        case_only = source.path.name.casefold() == destination.path.name.casefold()
        if destination.path.exists() and not case_only:
            raise FolderConflictError("The destination folder already exists.")
        try:
            if case_only:
                temporary = source.path.with_name(f".omega-folder-rename-{uuid4().hex}")
                os.rename(source.path, temporary)
                try:
                    os.rename(temporary, destination.path)
                except OSError:
                    os.rename(temporary, source.path)
                    raise
            else:
                os.rename(source.path, destination.path)
        except OSError as error:
            raise FolderOperationError(
                "The folder could not be renamed safely."
            ) from error
        case_verified = True
        if case_only:
            try:
                names = {entry.name for entry in destination.path.parent.iterdir()}
                case_verified = (
                    destination.path.name in names and source.path.name not in names
                )
            except OSError:
                case_verified = False
        source_remains = source.path.exists() and not case_only
        if (
            source_remains
            or not case_verified
            or not destination.path.is_dir()
            or is_link_or_reparse(destination.path)
        ):
            raise FolderOperationError("The folder rename could not be verified.")

    def copy(
        self,
        source: ValidatedFolderPath,
        destination: ValidatedFolderPath,
        *,
        maximum_depth: int,
        maximum_items: int,
        maximum_bytes: int,
    ) -> FolderTreeSnapshot:
        snapshot = self.preflight(
            source,
            destination,
            maximum_depth=maximum_depth,
            maximum_items=maximum_items,
            maximum_bytes=maximum_bytes,
        )
        self._revalidate(source, snapshot, maximum_depth, maximum_items, maximum_bytes)
        try:
            with TemporaryDirectory(
                dir=destination.path.parent, prefix=".omega-folder-copy-"
            ) as temporary:
                staging = Path(temporary) / destination.path.name
                staging.mkdir(parents=False, exist_ok=False)
                self._copy_contents(source.path, staging)
                staged_target = ValidatedFolderPath(
                    destination.location,
                    destination.relative_path,
                    staging,
                )
                staged = self.inspector.scan_tree(
                    staged_target,
                    maximum_depth=maximum_depth,
                    maximum_items=maximum_items,
                    maximum_bytes=maximum_bytes,
                )
                self._require_equivalent(snapshot, staged)
                if destination.path.exists():
                    raise FolderConflictError("The destination folder already exists.")
                os.rename(staging, destination.path)
        except (FolderConflictError, FolderOperationError, FolderValidationError):
            raise
        except OSError as error:
            raise FolderOperationError(
                "The folder could not be copied; incomplete temporary data was "
                "cleaned up."
            ) from error
        verified = self.inspector.scan_tree(
            destination,
            maximum_depth=maximum_depth,
            maximum_items=maximum_items,
            maximum_bytes=maximum_bytes,
        )
        self._require_equivalent(snapshot, verified)
        return verified

    def move(
        self,
        source: ValidatedFolderPath,
        destination: ValidatedFolderPath,
        *,
        maximum_depth: int,
        maximum_items: int,
        maximum_bytes: int,
    ) -> FolderTreeSnapshot:
        snapshot = self.preflight(
            source,
            destination,
            maximum_depth=maximum_depth,
            maximum_items=maximum_items,
            maximum_bytes=maximum_bytes,
        )
        if not self._same_volume(source.path, destination.path.parent):
            raise FolderCrossVolumeMoveError(
                "That folder is on a different drive. Omega can copy it safely, "
                "but cross-drive folder removal is deferred until undo support "
                "is available."
            )
        self._revalidate(source, snapshot, maximum_depth, maximum_items, maximum_bytes)
        self._require_destination(destination)
        try:
            os.rename(source.path, destination.path)
        except FileExistsError as error:
            raise FolderConflictError(
                "The destination folder already exists."
            ) from error
        except OSError as error:
            raise FolderOperationError(
                "The folder could not be moved safely."
            ) from error
        try:
            if source.path.exists() or not destination.path.is_dir():
                raise FolderOperationError("The folder move could not be verified.")
            verified = self.inspector.scan_tree(
                destination,
                maximum_depth=maximum_depth,
                maximum_items=maximum_items,
                maximum_bytes=maximum_bytes,
            )
            self._require_equivalent(snapshot, verified)
            return verified
        except FolderOperationError:
            if not source.path.exists() and destination.path.exists():
                try:
                    os.rename(destination.path, source.path)
                except OSError as rollback_error:
                    raise FolderOperationError(
                        "The move could not be verified and automatic restoration "
                        "failed."
                    ) from rollback_error
            raise

    def _copy_contents(self, source: Path, destination: Path) -> None:
        try:
            with os.scandir(source) as stream:
                entries = sorted(stream, key=lambda entry: entry.name.casefold())
        except OSError as error:
            raise FolderOperationError(
                "A source folder could not be read during copy."
            ) from error
        for entry in entries:
            source_entry = Path(entry.path)
            destination_entry = destination / entry.name
            if is_link_or_reparse(source_entry):
                raise FolderValidationError(
                    "A symbolic link or junction appeared during the copy."
                )
            try:
                if entry.is_dir(follow_symlinks=False):
                    destination_entry.mkdir(parents=False, exist_ok=False)
                    self._copy_contents(source_entry, destination_entry)
                elif entry.is_file(follow_symlinks=False):
                    shutil.copyfile(
                        source_entry, destination_entry, follow_symlinks=False
                    )
                else:
                    raise FolderValidationError(
                        "The source contains an unsupported filesystem entry."
                    )
            except (FolderValidationError, FolderOperationError):
                raise
            except OSError as error:
                raise FolderOperationError(
                    "A folder entry could not be copied."
                ) from error

    def _revalidate(
        self,
        source: ValidatedFolderPath,
        expected: FolderTreeSnapshot,
        maximum_depth: int,
        maximum_items: int,
        maximum_bytes: int,
    ) -> None:
        current = self.inspector.scan_tree(
            source,
            maximum_depth=maximum_depth,
            maximum_items=maximum_items,
            maximum_bytes=maximum_bytes,
        )
        if current != expected:
            raise FolderOperationError(
                "The source folder changed while Omega prepared the operation. "
                "Please try again."
            )

    @staticmethod
    def _require_equivalent(
        expected: FolderTreeSnapshot, actual: FolderTreeSnapshot
    ) -> None:
        if (
            expected.file_count,
            expected.folder_count,
            expected.total_bytes,
        ) != (actual.file_count, actual.folder_count, actual.total_bytes):
            raise FolderOperationError("The copied folder tree could not be verified.")

    def _require_source(self, source: ValidatedFolderPath) -> None:
        if not source.path.exists():
            raise FolderOperationError("The source folder was not found.")
        if is_link_or_reparse(source.path) or not source.path.is_dir():
            raise FolderValidationError("The source must be a real directory.")
        if self.validator.is_protected_path(source.path):
            raise FolderValidationError("That source folder is protected.")

    @staticmethod
    def _require_destination(destination: ValidatedFolderPath) -> None:
        parent = destination.path.parent
        if not parent.exists() or not parent.is_dir() or is_link_or_reparse(parent):
            raise FolderOperationError("The destination parent folder does not exist.")
        if destination.path.exists():
            raise FolderConflictError("The destination folder already exists.")

    @staticmethod
    def _same_volume(source: Path, destination_parent: Path) -> bool:
        try:
            return source.stat().st_dev == destination_parent.stat().st_dev
        except OSError:
            return source.drive.casefold() == destination_parent.drive.casefold()

    @staticmethod
    def _same_path(first: Path, second: Path) -> bool:
        return os.path.normcase(first) == os.path.normcase(second)

    @staticmethod
    def _contained(candidate: Path, root: Path) -> bool:
        try:
            return os.path.commonpath(
                (os.path.normcase(candidate), os.path.normcase(root))
            ) == os.path.normcase(root)
        except ValueError:
            return False
