"""Bounded folder listing, metadata inspection, and tree preflight."""

from __future__ import annotations

import os
import stat
from datetime import UTC, datetime
from heapq import nsmallest
from pathlib import Path

from omega.core.exceptions import (
    FolderInspectionError,
    FolderResourceLimitError,
    FolderValidationError,
)
from omega.folders.results import (
    FolderListing,
    FolderMetadata,
    FolderTreeSnapshot,
    ValidatedFolderPath,
)
from omega.folders.validator import FolderPathValidator, is_link_or_reparse


def _safe_name(name: str) -> str:
    return "".join(
        "?" if ord(character) < 32 or ord(character) == 127 else character
        for character in name
    )


class FolderInspector:
    """Inspect real directories without following links or scanning without bounds."""

    def __init__(self, validator: FolderPathValidator) -> None:
        self.validator = validator

    @staticmethod
    def exists(target: ValidatedFolderPath) -> bool:
        return (
            target.path.exists()
            and target.path.is_dir()
            and not is_link_or_reparse(target.path)
        )

    def list_folder(self, target: ValidatedFolderPath, limit: int) -> FolderListing:
        self._require_directory(target.path)
        folders: list[str] = []
        files: list[str] = []
        skipped = 0
        try:
            with os.scandir(target.path) as stream:
                entries = nsmallest(
                    limit + 1,
                    (Path(entry.path) for entry in stream),
                    key=lambda item: item.name.casefold(),
                )
        except OSError as error:
            raise FolderInspectionError(
                "The folder contents could not be read."
            ) from error
        truncated = len(entries) > limit
        for entry in entries[:limit]:
            try:
                if is_link_or_reparse(entry) or self.validator.is_protected_path(entry):
                    skipped += 1
                elif entry.is_dir():
                    folders.append(_safe_name(entry.name))
                elif entry.is_file():
                    files.append(_safe_name(entry.name))
                else:
                    skipped += 1
            except OSError:
                skipped += 1
        return FolderListing(tuple(folders), tuple(files), truncated, skipped)

    def metadata(
        self,
        target: ValidatedFolderPath,
        *,
        recursive: bool,
        maximum_depth: int,
        maximum_items: int,
        maximum_bytes: int,
    ) -> FolderMetadata:
        self._require_directory(target.path)
        listing = self.list_folder(target, maximum_items)
        try:
            details = target.path.stat()
        except OSError as error:
            raise FolderInspectionError("Folder metadata could not be read.") from error
        snapshot = None
        if recursive:
            snapshot = self.scan_tree(
                target,
                maximum_depth=maximum_depth,
                maximum_items=maximum_items,
                maximum_bytes=maximum_bytes,
                strict_limits=False,
                reject_inaccessible=False,
            )
        relative = (
            "" if target.relative_path == Path(".") else target.relative_path.as_posix()
        )
        return FolderMetadata(
            name=target.path.name or target.location.display_name,
            logical_location=target.location.logical_name,
            relative_path=relative,
            immediate_file_count=len(listing.files),
            immediate_folder_count=len(listing.folders),
            created_at=datetime.fromtimestamp(details.st_ctime, UTC),
            modified_at=datetime.fromtimestamp(details.st_mtime, UTC),
            read_only=not bool(details.st_mode & stat.S_IWRITE),
            recursive_file_count=snapshot.file_count if snapshot else None,
            recursive_folder_count=snapshot.folder_count if snapshot else None,
            total_bytes=snapshot.total_bytes if snapshot else None,
            maximum_depth=snapshot.maximum_depth if snapshot else None,
            truncated=(listing.truncated or bool(snapshot and snapshot.incomplete)),
        )

    def scan_tree(
        self,
        target: ValidatedFolderPath,
        *,
        maximum_depth: int,
        maximum_items: int,
        maximum_bytes: int,
        strict_limits: bool = True,
        reject_inaccessible: bool = True,
    ) -> FolderTreeSnapshot:
        """Measure a tree incrementally and reject links before mutation."""
        self._require_directory(target.path)
        try:
            root_details = target.path.stat()
            with os.scandir(target.path) as stream:
                immediate = sum(1 for _ in stream)
        except OSError as error:
            raise FolderInspectionError("The folder could not be inspected.") from error
        files = folders = total_bytes = deepest = 0
        incomplete = False
        stack: list[tuple[Path, int]] = [(target.path, 0)]
        while stack:
            directory, depth = stack.pop()
            try:
                with os.scandir(directory) as stream:
                    entries = sorted(stream, key=lambda entry: entry.name.casefold())
            except OSError as error:
                if reject_inaccessible:
                    raise FolderInspectionError(
                        "A folder entry could not be inspected."
                    ) from error
                incomplete = True
                continue
            for entry in entries:
                path = Path(entry.path)
                if is_link_or_reparse(path):
                    raise FolderValidationError(
                        "A symbolic link or junction was found in the folder tree."
                    )
                if self.validator.is_protected_path(path):
                    raise FolderValidationError(
                        "A protected folder was found in the tree."
                    )
                try:
                    if entry.is_dir(follow_symlinks=False):
                        folders += 1
                        child_depth = depth + 1
                        deepest = max(deepest, child_depth)
                        if child_depth > maximum_depth:
                            if strict_limits:
                                raise FolderResourceLimitError(
                                    "That folder exceeds Omega's safe depth limit."
                                )
                            incomplete = True
                        else:
                            stack.append((path, child_depth))
                    elif entry.is_file(follow_symlinks=False):
                        files += 1
                        total_bytes += entry.stat(follow_symlinks=False).st_size
                    else:
                        raise FolderValidationError(
                            "The folder contains an unsupported filesystem entry."
                        )
                except OSError as error:
                    if reject_inaccessible:
                        raise FolderInspectionError(
                            "A folder entry could not be inspected."
                        ) from error
                    incomplete = True
                    continue
                exceeded = (
                    files + folders > maximum_items or total_bytes > maximum_bytes
                )
                if exceeded:
                    if strict_limits:
                        raise FolderResourceLimitError(
                            "That folder is too large for Omega to process safely."
                        )
                    incomplete = True
                    stack.clear()
                    break
        return FolderTreeSnapshot(
            files,
            folders,
            total_bytes,
            deepest,
            root_details.st_mtime_ns,
            immediate,
            incomplete,
        )

    @staticmethod
    def _require_directory(path: Path) -> None:
        if not path.exists():
            raise FolderInspectionError("The requested folder was not found.")
        if is_link_or_reparse(path) or not path.is_dir():
            raise FolderInspectionError("The target must be a real directory.")
