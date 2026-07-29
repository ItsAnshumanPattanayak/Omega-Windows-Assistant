"""Bounded read-only performance diagnostics with privacy-safe labels."""

from __future__ import annotations

import sqlite3
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from statistics import median
from time import perf_counter
from typing import TYPE_CHECKING, TypeVar

from omega.performance.configuration import PerformanceConfiguration

if TYPE_CHECKING:
    from omega.config.settings import Settings

T = TypeVar("T")


@dataclass(frozen=True, slots=True)
class PerformanceMeasurement:
    operation: str
    minimum_ms: float
    median_ms: float
    maximum_ms: float
    runs: int
    kind: str = "measurement"


@dataclass(frozen=True, slots=True)
class PerformanceReport:
    available: bool
    measurements: tuple[PerformanceMeasurement, ...]
    enabled_subsystems: int
    database_exists: bool
    database_size_bytes: int
    migration_version: int | None
    notes: tuple[str, ...]


class PerformanceDiagnostics:
    """Measure only local, non-mutating operations with fixed safe labels."""

    def __init__(
        self,
        configuration: PerformanceConfiguration,
        *,
        repository_root: Path,
        clock: Callable[[], float] = perf_counter,
    ) -> None:
        self.configuration = configuration
        self.repository_root = repository_root.resolve(strict=False)
        self._clock = clock

    def run(self, settings: Settings) -> PerformanceReport:
        if not self.configuration.enabled:
            return PerformanceReport(False, (), 0, False, 0, None, ("disabled",))

        from omega.config import load_settings
        from omega.understanding import CommandParser

        runs = self.configuration.diagnostic_runs
        measurements = (
            self._measure("configuration_load", load_settings, runs),
            self._measure(
                "parser_initialize",
                lambda: CommandParser(
                    security_configuration=settings.security_configuration,
                    intent_cache_size=self.configuration.parser_cache_size,
                ),
                runs,
            ),
        )
        parser = CommandParser(
            security_configuration=settings.security_configuration,
            intent_cache_size=self.configuration.parser_cache_size,
        )
        commands = (
            "Open Chrome",
            "Show my preferences",
            "Search knowledge for security",
            "List unread emails",
            "Show calendar agenda",
            "Run workflow Morning",
        )
        parse_measurement = self._measure(
            "parse_representative_batch",
            lambda: tuple(parser.parse(command) for command in commands),
            runs,
        )

        sections = (
            settings.voice,
            settings.browser,
            settings.system,
            settings.scheduling,
            settings.productivity,
            settings.knowledge,
            settings.email,
            settings.calendar,
            settings.desktop_utilities,
            settings.workflows,
            settings.plugins,
            settings.local_ai,
            settings.personalization,
            settings.accessibility,
            settings.localization,
        )
        enabled_subsystems = sum(section.get("enabled") is True for section in sections)
        database_path = settings.database_configuration.resolve_path()
        database_exists = database_path.is_file()
        database_size = database_path.stat().st_size if database_exists else 0
        migration_version = self._migration_version(database_path)
        return PerformanceReport(
            True,
            (*measurements, parse_measurement),
            enabled_subsystems,
            database_exists,
            database_size,
            migration_version,
            (
                "Measurements are local process timings, not universal guarantees.",
                "No private command text or provider content is reported.",
            ),
        )

    def _measure(
        self, operation: str, callback: Callable[[], T], runs: int
    ) -> PerformanceMeasurement:
        values: list[float] = []
        for _ in range(runs):
            started_at = self._clock()
            callback()
            values.append(max(0.0, (self._clock() - started_at) * 1_000))
        return PerformanceMeasurement(
            operation,
            min(values),
            median(values),
            max(values),
            len(values),
        )

    @staticmethod
    def _migration_version(database_path: Path) -> int | None:
        if not database_path.is_file():
            return None
        try:
            uri = database_path.resolve().as_uri() + "?mode=ro"
            with sqlite3.connect(uri, uri=True, timeout=1.0) as connection:
                row = connection.execute(
                    "SELECT MAX(version) FROM schema_migrations"
                ).fetchone()
            return None if row is None or row[0] is None else int(row[0])
        except sqlite3.Error:
            return None


def format_performance_report(report: PerformanceReport) -> str:
    lines = ["Omega performance diagnostics"]
    if not report.available:
        return "\n".join((*lines, "STATUS: DISABLED"))
    for item in report.measurements:
        lines.append(
            f"MEASURED {item.operation}: min={item.minimum_ms:.3f} ms "
            f"median={item.median_ms:.3f} ms max={item.maximum_ms:.3f} ms "
            f"runs={item.runs}"
        )
    lines.extend(
        (
            f"ENABLED_SUBSYSTEMS: {report.enabled_subsystems}",
            f"DATABASE_PRESENT: {str(report.database_exists).lower()}",
            f"DATABASE_SIZE_BYTES: {report.database_size_bytes}",
            "MIGRATION_VERSION: "
            + (
                "unavailable"
                if report.migration_version is None
                else str(report.migration_version)
            ),
        )
    )
    lines.extend(f"NOTE: {note}" for note in report.notes)
    lines.append("RESULT: PASS")
    return "\n".join(lines)
