"""Stable definitions and validated settings for controlled file operations."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from omega.core.exceptions import ModelValidationError

LOGICAL_LOCATIONS = (
    "desktop",
    "documents",
    "downloads",
    "pictures",
    "music",
    "videos",
    "home",
    "current_directory",
)

LOCATION_ALIASES = {
    "desktop": "desktop",
    "my desktop": "desktop",
    "documents": "documents",
    "my documents": "documents",
    "downloads": "downloads",
    "my downloads": "downloads",
    "pictures": "pictures",
    "my pictures": "pictures",
    "music": "music",
    "my music": "music",
    "videos": "videos",
    "my videos": "videos",
    "home": "home",
    "home folder": "home",
    "user folder": "home",
    "current directory": "current_directory",
    "current folder": "current_directory",
    "project directory": "current_directory",
    "current_directory": "current_directory",
}

TEXT_EXTENSIONS = frozenset(
    {".txt", ".md", ".json", ".csv", ".py", ".html", ".css", ".js", ".yaml", ".yml"}
)
OPEN_DOCUMENT_EXTENSIONS = frozenset(
    {".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx"}
)
BLOCKED_EXTENSIONS = frozenset(
    {
        ".exe",
        ".dll",
        ".bat",
        ".cmd",
        ".ps1",
        ".vbs",
        ".scr",
        ".msi",
        ".reg",
        ".sys",
        ".com",
        ".jar",
        ".url",
        ".lnk",
    }
)
OPEN_EXTENSIONS = TEXT_EXTENSIONS.difference({".js", ".py"}) | OPEN_DOCUMENT_EXTENSIONS


@dataclass(frozen=True)
class FileOperationSettings:
    """Validated resource limits and fail-closed Phase 5 policy switches."""

    default_location: str = "desktop"
    maximum_read_size_bytes: int = 1_048_576
    maximum_display_characters: int = 10_000
    maximum_write_size_bytes: int = 1_048_576
    maximum_resulting_file_size_bytes: int = 5_242_880
    search_max_depth: int = 5
    search_max_results: int = 50
    allow_absolute_paths: bool = False
    allow_permanent_deletion: bool = False

    def __post_init__(self) -> None:
        if self.default_location not in LOGICAL_LOCATIONS:
            raise ModelValidationError("default_location must be registered.")
        positive = (
            self.maximum_read_size_bytes,
            self.maximum_display_characters,
            self.maximum_write_size_bytes,
            self.maximum_resulting_file_size_bytes,
            self.search_max_results,
        )
        if any(isinstance(value, bool) or value <= 0 for value in positive):
            raise ModelValidationError(
                "File size, timeout, and result limits must be positive."
            )
        if not 0 <= self.search_max_depth <= 20:
            raise ModelValidationError("search_max_depth must be between 0 and 20.")
        if self.search_max_results > 500:
            raise ModelValidationError("search_max_results must not exceed 500.")
        if self.allow_absolute_paths or self.allow_permanent_deletion:
            raise ModelValidationError(
                "Unsafe Phase 5 file-policy switches must remain disabled."
            )

    @classmethod
    def from_mapping(cls, values: Mapping[str, Any]) -> FileOperationSettings:
        """Create typed operation settings from the application configuration."""
        return cls(
            default_location=str(values.get("default_location", "desktop")),
            maximum_read_size_bytes=int(
                values.get("maximum_read_size_bytes", 1_048_576)
            ),
            maximum_display_characters=int(
                values.get("maximum_display_characters", 10_000)
            ),
            maximum_write_size_bytes=int(
                values.get("maximum_write_size_bytes", 1_048_576)
            ),
            maximum_resulting_file_size_bytes=int(
                values.get("maximum_resulting_file_size_bytes", 5_242_880)
            ),
            search_max_depth=int(values.get("search_max_depth", 5)),
            search_max_results=int(values.get("search_max_results", 50)),
            allow_absolute_paths=bool(values.get("allow_absolute_paths", False)),
            allow_permanent_deletion=bool(
                values.get("allow_permanent_deletion", False)
            ),
        )
