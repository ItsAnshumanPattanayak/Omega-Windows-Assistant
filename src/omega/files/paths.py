"""Composition of logical-location resolution and final path validation."""

from __future__ import annotations

from omega.files.locations import FileLocationResolver
from omega.files.results import ValidatedFilePath
from omega.files.validator import FilePathValidator


class SafeFilePathResolver:
    """Resolve a logical root and produce one validated contained file path."""

    def __init__(
        self, location_resolver: FileLocationResolver, validator: FilePathValidator
    ) -> None:
        self.location_resolver = location_resolver
        self.validator = validator

    def resolve(self, location: str, relative_path: str) -> ValidatedFilePath:
        """Resolve and validate without accepting an arbitrary absolute path."""
        return self.validator.require_file_path(
            self.location_resolver.resolve(location), relative_path
        )
