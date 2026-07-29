"""Developer-facing repeatable benchmark entry point."""

from __future__ import annotations

from omega.config import load_settings
from omega.performance.diagnostics import (
    PerformanceDiagnostics,
    format_performance_report,
)
from omega.utils.paths import project_root


def main() -> int:
    settings = load_settings()
    report = PerformanceDiagnostics(
        settings.performance_configuration, repository_root=project_root()
    ).run(settings)
    print(format_performance_report(report))
    return 0 if report.available else 1


if __name__ == "__main__":
    raise SystemExit(main())
