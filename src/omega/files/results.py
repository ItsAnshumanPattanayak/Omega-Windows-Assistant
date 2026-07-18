"""Immutable internal records for controlled file resolution and inspection."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


@dataclass(frozen=True)
class ResolvedLocation:
    """An approved logical location resolved to an absolute directory."""

    logical_name: str
    display_name: str
    root: Path


@dataclass(frozen=True)
class ValidatedFilePath:
    """A file target proven to be contained by one approved logical root."""

    location: ResolvedLocation
    relative_path: Path
    path: Path


@dataclass(frozen=True)
class PathValidationOutcome:
    """Structured non-throwing result for path-validation callers."""

    valid: bool
    validated_path: ValidatedFilePath | None = None
    code: str | None = None
    message: str | None = None


@dataclass(frozen=True)
class FileMetadata:
    """Safe metadata intended for user-facing serialization."""

    name: str
    logical_location: str
    relative_path: str
    size_bytes: int
    created_at: datetime
    modified_at: datetime
    extension: str
    read_only: bool


@dataclass(frozen=True)
class FileSearchMatch:
    """A bounded search match without a private absolute path."""

    name: str
    logical_location: str
    relative_path: str


@dataclass(frozen=True)
class TextReadResult:
    """Sanitized bounded text prepared for terminal display."""

    content: str
    truncated: bool
    size_bytes: int


@dataclass(frozen=True)
class FileSnapshot:
    """Metadata used to bind an overwrite confirmation to one file version."""

    size_bytes: int
    modified_time_ns: int
    content_hash: str
