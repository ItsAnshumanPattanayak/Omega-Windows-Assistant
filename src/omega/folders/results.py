"""Immutable internal records for bounded folder operations."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from omega.files.results import ResolvedLocation


@dataclass(frozen=True)
class ValidatedFolderPath:
    """A directory target proven contained by an approved logical root."""

    location: ResolvedLocation
    relative_path: Path
    path: Path


@dataclass(frozen=True)
class FolderListing:
    """One bounded, non-recursive directory listing."""

    folders: tuple[str, ...]
    files: tuple[str, ...]
    truncated: bool
    skipped_entries: int = 0


@dataclass(frozen=True)
class FolderTreeSnapshot:
    """Bounded regular-file tree measurements captured during preflight."""

    file_count: int
    folder_count: int
    total_bytes: int
    maximum_depth: int
    root_modified_time_ns: int
    immediate_item_count: int
    incomplete: bool = False

    @property
    def total_items(self) -> int:
        return self.file_count + self.folder_count


@dataclass(frozen=True)
class FolderMetadata:
    """Safe folder metadata without private absolute paths."""

    name: str
    logical_location: str
    relative_path: str
    immediate_file_count: int
    immediate_folder_count: int
    created_at: datetime
    modified_at: datetime
    read_only: bool
    recursive_file_count: int | None = None
    recursive_folder_count: int | None = None
    total_bytes: int | None = None
    maximum_depth: int | None = None
    truncated: bool = False


@dataclass(frozen=True)
class FolderSearchMatch:
    """A folder-name match represented relative to its approved root."""

    name: str
    logical_location: str
    relative_path: str
