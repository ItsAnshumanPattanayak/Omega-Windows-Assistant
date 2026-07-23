"""Typed configuration for recoverable Phase 8 operations."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from omega.core.exceptions import ConfigurationError


@dataclass(frozen=True)
class RecoveryConfiguration:
    """Validated limits and immutable boundaries for recovery operations."""

    enabled: bool = True
    allow_permanent_deletion: bool = False
    require_confirmation_for_recycle: bool = True
    require_confirmation_for_restore: bool = True
    undo_timeout_seconds: int = 300
    maximum_undo_records: int = 20
    maximum_recycle_size_bytes: int = 5_368_709_120
    persist_undo_records: bool = False

    def __post_init__(self) -> None:
        boolean_fields = (
            "enabled",
            "allow_permanent_deletion",
            "require_confirmation_for_recycle",
            "require_confirmation_for_restore",
            "persist_undo_records",
        )

        for field_name in boolean_fields:
            if not isinstance(getattr(self, field_name), bool):
                raise ConfigurationError(f"recovery.{field_name} must be a boolean.")

        if self.allow_permanent_deletion:
            raise ConfigurationError("Phase 8 does not permit permanent deletion.")

        if (
            isinstance(self.undo_timeout_seconds, bool)
            or not isinstance(self.undo_timeout_seconds, int)
            or not 10 <= self.undo_timeout_seconds <= 3_600
        ):
            raise ConfigurationError(
                "recovery.undo_timeout_seconds must be between " "10 and 3600."
            )

        if (
            isinstance(self.maximum_undo_records, bool)
            or not isinstance(self.maximum_undo_records, int)
            or not 1 <= self.maximum_undo_records <= 100
        ):
            raise ConfigurationError(
                "recovery.maximum_undo_records must be between 1 and 100."
            )

        if (
            isinstance(self.maximum_recycle_size_bytes, bool)
            or not isinstance(self.maximum_recycle_size_bytes, int)
            or self.maximum_recycle_size_bytes <= 0
        ):
            raise ConfigurationError(
                "recovery.maximum_recycle_size_bytes must be positive."
            )

        maximum_supported_bytes = 53_687_091_200

        if self.maximum_recycle_size_bytes > maximum_supported_bytes:
            raise ConfigurationError(
                "recovery.maximum_recycle_size_bytes must not exceed " "50 GiB."
            )

    @classmethod
    def from_mapping(
        cls,
        values: Mapping[str, Any],
    ) -> RecoveryConfiguration:
        """Create validated configuration from a mapping."""

        if not isinstance(values, Mapping):
            raise ConfigurationError(
                "Configuration section 'recovery' must be a mapping."
            )

        known_fields = {
            "enabled",
            "allow_permanent_deletion",
            "require_confirmation_for_recycle",
            "require_confirmation_for_restore",
            "undo_timeout_seconds",
            "maximum_undo_records",
            "maximum_recycle_size_bytes",
            "persist_undo_records",
        }

        unknown_fields = set(values).difference(known_fields)

        if unknown_fields:
            unknown = ", ".join(
                sorted(str(field_name) for field_name in unknown_fields)
            )
            raise ConfigurationError(
                f"Unknown recovery configuration field(s): {unknown}"
            )

        return cls(**dict(values))
