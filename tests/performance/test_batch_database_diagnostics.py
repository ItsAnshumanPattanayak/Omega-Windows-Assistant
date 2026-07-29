from pathlib import Path

from omega.config import load_settings
from omega.database import DatabaseConfiguration, DatabaseConnectionFactory
from omega.performance import PerformanceConfiguration
from omega.performance.diagnostics import (
    PerformanceDiagnostics,
    format_performance_report,
)
from omega.personalization import FakePreferenceRepository, PreferenceResolver
from omega.personalization.models import UserProfile
from omega.utils.paths import project_root


class CountingPreferenceRepository(FakePreferenceRepository):
    def __init__(self) -> None:
        super().__init__()
        self.active_reads = 0
        self.preference_reads = 0

    def active_profile_id(self) -> str | None:
        self.active_reads += 1
        return super().active_profile_id()

    def list_preferences(self, profile_id: str):  # type: ignore[no-untyped-def]
        self.preference_reads += 1
        return super().list_preferences(profile_id)


def test_preference_batch_uses_two_repository_reads() -> None:
    repository = CountingPreferenceRepository()
    profile = UserProfile("Default", is_default=True)
    repository.save_profile(profile)
    repository.set_active_profile(profile.profile_id)
    resolver = PreferenceResolver(repository)
    result = resolver.resolve_many(("language", "time_format", "display_name"))
    assert set(result) == {"language", "time_format", "display_name"}
    assert repository.active_reads == 1
    assert repository.preference_reads == 1


def test_database_factory_reuses_persistent_journal_setup(tmp_path: Path) -> None:
    factory = DatabaseConnectionFactory(
        DatabaseConfiguration(), database_path=tmp_path / "measured.db"
    )
    with factory.connect() as first:
        assert first.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
    with factory.connect() as second:
        assert second.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        assert second.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
    assert factory._journal_mode_initialized  # noqa: SLF001


def test_performance_diagnostic_disabled_behavior() -> None:
    settings = load_settings()
    report = PerformanceDiagnostics(
        PerformanceConfiguration(enabled=False), repository_root=project_root()
    ).run(settings)
    assert not report.available
    assert format_performance_report(report).endswith("STATUS: DISABLED")


def test_performance_diagnostic_is_bounded_and_redacted() -> None:
    settings = load_settings()
    report = PerformanceDiagnostics(
        PerformanceConfiguration(diagnostic_runs=3), repository_root=project_root()
    ).run(settings)
    rendered = format_performance_report(report)
    assert report.available and len(report.measurements) == 3
    assert "RESULT: PASS" in rendered
    assert "email body" not in rendered.casefold()
    assert "clipboard content" not in rendered.casefold()
