"""Conservative, privacy-preserving performance configuration."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, fields
from typing import Any

from omega.core.exceptions import PerformanceConfigurationError


@dataclass(frozen=True, slots=True)
class PerformanceConfiguration:
    enabled: bool = True
    collect_local_timing_metrics: bool = False
    maximum_timing_records: int = 500
    diagnostic_runs: int = 7
    parser_cache_size: int = 256
    workflow_plan_cache_size: int = 50
    plugin_manifest_cache_size: int = 100
    enable_sensitive_content_caching: bool = False
    enable_telemetry: bool = False

    def __post_init__(self) -> None:
        boolean_names = {
            "enabled",
            "collect_local_timing_metrics",
            "enable_sensitive_content_caching",
            "enable_telemetry",
        }
        for name in boolean_names:
            if not isinstance(getattr(self, name), bool):
                raise PerformanceConfigurationError(
                    f"performance.{name} must be boolean."
                )
        bounds: dict[str, tuple[int, int]] = {
            "maximum_timing_records": (1, 10_000),
            "diagnostic_runs": (3, 25),
            "parser_cache_size": (0, 4_096),
            "workflow_plan_cache_size": (0, 1_000),
            "plugin_manifest_cache_size": (0, 2_000),
        }
        for name, (minimum, maximum) in bounds.items():
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int):
                raise PerformanceConfigurationError(
                    f"performance.{name} must be an integer."
                )
            if not minimum <= value <= maximum:
                raise PerformanceConfigurationError(
                    f"performance.{name} is outside its safe bounds."
                )
        if self.enable_sensitive_content_caching or self.enable_telemetry:
            raise PerformanceConfigurationError(
                "Sensitive caching and telemetry must remain disabled."
            )

    @classmethod
    def from_mapping(cls, values: Mapping[str, Any]) -> PerformanceConfiguration:
        known = {item.name for item in fields(cls)}
        unknown = set(values) - known
        if unknown:
            raise PerformanceConfigurationError(
                "Unknown performance setting(s): " + ", ".join(sorted(unknown))
            )
        return cls(**dict(values))
