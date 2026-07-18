"""Validated settings for controlled Phase 6 folder operations."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from omega.core.exceptions import ModelValidationError
from omega.files.definitions import LOGICAL_LOCATIONS


@dataclass(frozen=True)
class FolderOperationSettings:
    """Bounded resource limits with all destructive policy switches fail-closed."""

    default_location: str = "desktop"
    maximum_listing_items: int = 100
    maximum_scan_depth: int = 10
    maximum_scan_items: int = 10_000
    maximum_scan_bytes: int = 10_737_418_240
    maximum_copy_depth: int = 20
    maximum_copy_items: int = 10_000
    maximum_copy_bytes: int = 5_368_709_120
    search_max_depth: int = 6
    search_max_results: int = 50
    allow_folder_merge: bool = False
    allow_destination_replace: bool = False
    allow_permanent_deletion: bool = False
    allow_cross_volume_move: bool = False

    def __post_init__(self) -> None:
        if self.default_location not in LOGICAL_LOCATIONS:
            raise ModelValidationError("default_location must be registered.")
        positive = (
            self.maximum_listing_items,
            self.maximum_scan_items,
            self.maximum_scan_bytes,
            self.maximum_copy_items,
            self.maximum_copy_bytes,
            self.search_max_results,
        )
        if any(isinstance(value, bool) or value <= 0 for value in positive):
            raise ModelValidationError("Folder item and byte limits must be positive.")
        depths = (
            self.maximum_scan_depth,
            self.maximum_copy_depth,
            self.search_max_depth,
        )
        if any(isinstance(value, bool) or not 0 <= value <= 50 for value in depths):
            raise ModelValidationError("Folder depth limits must be between 0 and 50.")
        if self.maximum_listing_items > 1_000 or self.search_max_results > 500:
            raise ModelValidationError("Folder display limits are too large.")
        if any(
            (
                self.allow_folder_merge,
                self.allow_destination_replace,
                self.allow_permanent_deletion,
                self.allow_cross_volume_move,
            )
        ):
            raise ModelValidationError(
                "Unsafe Phase 6 folder-policy switches must remain disabled."
            )

    @classmethod
    def from_mapping(cls, values: Mapping[str, Any]) -> FolderOperationSettings:
        """Create typed folder settings from application configuration."""
        return cls(
            default_location=str(values.get("default_location", "desktop")),
            maximum_listing_items=int(values.get("maximum_listing_items", 100)),
            maximum_scan_depth=int(values.get("maximum_scan_depth", 10)),
            maximum_scan_items=int(values.get("maximum_scan_items", 10_000)),
            maximum_scan_bytes=int(values.get("maximum_scan_bytes", 10_737_418_240)),
            maximum_copy_depth=int(values.get("maximum_copy_depth", 20)),
            maximum_copy_items=int(values.get("maximum_copy_items", 10_000)),
            maximum_copy_bytes=int(values.get("maximum_copy_bytes", 5_368_709_120)),
            search_max_depth=int(values.get("search_max_depth", 6)),
            search_max_results=int(values.get("search_max_results", 50)),
            allow_folder_merge=bool(values.get("allow_folder_merge", False)),
            allow_destination_replace=bool(
                values.get("allow_destination_replace", False)
            ),
            allow_permanent_deletion=bool(
                values.get("allow_permanent_deletion", False)
            ),
            allow_cross_volume_move=bool(values.get("allow_cross_volume_move", False)),
        )
