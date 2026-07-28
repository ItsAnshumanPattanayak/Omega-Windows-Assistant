from __future__ import annotations

from pathlib import Path

import pytest

from omega.database import (
    DatabaseConfiguration,
    DatabaseConnectionFactory,
    MigrationRunner,
)
from omega.database.schema import LATEST_SCHEMA_VERSION
from omega.models import CommandSource, IntentType
from omega.personalization import (
    PersonalizationConfiguration,
    PreferenceResolver,
    PreferenceService,
    PreferenceValidator,
    SqlitePreferenceRepository,
)
from omega.understanding import CommandParser


def _factory(tmp_path: Path) -> DatabaseConnectionFactory:
    return DatabaseConnectionFactory(
        DatabaseConfiguration(), database_path=tmp_path / "omega.db"
    )


def test_phase_24_migration_is_contiguous_and_creates_bounded_tables(
    tmp_path: Path,
) -> None:
    factory = _factory(tmp_path)
    assert MigrationRunner(factory).migrate() == LATEST_SCHEMA_VERSION == 14
    with factory.connect() as connection:
        versions = [
            int(row[0])
            for row in connection.execute(
                "SELECT version FROM schema_migrations ORDER BY version"
            )
        ]
        tables = {
            str(row[0])
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
        assert versions == list(range(1, 15))
        assert {
            "user_profiles",
            "preference_values",
            "profile_activation",
            "plugin_preference_values",
        }.issubset(tables)
        assert int(connection.execute("PRAGMA foreign_keys").fetchone()[0]) == 1


def test_existing_database_upgrade_preserves_phase_23_data(tmp_path: Path) -> None:
    factory = _factory(tmp_path)
    runner = MigrationRunner(factory)
    assert runner.migrate(target_version=13) == 13
    with factory.connect() as connection:
        connection.execute(
            """INSERT INTO plugin_installations
               (plugin_id,version,fingerprint,display_name,status,source_path,updated_at)
               VALUES (?,?,?,?,?,?,?)""",
            (
                "example.plugin",
                "1.0.0",
                "a" * 64,
                "Example",
                "disabled",
                "plugins/example",
                "2025-01-01T00:00:00+00:00",
            ),
        )
    assert runner.migrate() == 14
    with factory.connect() as connection:
        assert (
            connection.execute("SELECT COUNT(*) FROM plugin_installations").fetchone()[
                0
            ]
            == 1
        )


def test_sqlite_preference_round_trip(tmp_path: Path) -> None:
    factory = _factory(tmp_path)
    MigrationRunner(factory).migrate()
    repository = SqlitePreferenceRepository(factory)
    configuration = PersonalizationConfiguration()
    service = PreferenceService(
        configuration,
        repository,
        PreferenceValidator(configuration, application_aliases=("chrome",)),
        PreferenceResolver(repository),
    )
    service.set_preference("default_browser", "chrome")
    assert service.resolver.resolve("default_browser").value == "chrome"
    service_again = PreferenceService(
        configuration,
        repository,
        PreferenceValidator(configuration, application_aliases=("chrome",)),
        PreferenceResolver(repository),
    )
    assert service_again.resolver.resolve("default_browser").value == "chrome"


@pytest.mark.parametrize(
    ("text", "intent"),
    [
        ("Show my profile", IntentType.SHOW_PROFILE),
        ("Show my preferences", IntentType.SHOW_PREFERENCES),
        ("Show my privacy preferences", IntentType.SHOW_PRIVACY_PREFERENCES),
        ("Show what Omega remembers about me", IntentType.SHOW_REMEMBERED_PREFERENCES),
        ("Call me Anshuman", IntentType.SET_PREFERENCE),
        ("Keep responses concise", IntentType.SET_PREFERENCE),
        ("Use 24-hour time", IntentType.SET_PREFERENCE),
        ("Be concise for this session", IntentType.SET_SESSION_PREFERENCE),
        ("Reset session preferences", IntentType.RESET_SESSION_PREFERENCES),
        ("Reset voice preferences", IntentType.RESET_PREFERENCE_CATEGORY),
        ("Reset all preferences", IntentType.RESET_ALL_PREFERENCES),
        ("Export my profile", IntentType.EXPORT_PROFILE),
        ("Import profile from profile.json", IntentType.IMPORT_PROFILE),
        ("List profiles", IntentType.LIST_PROFILES),
    ],
)
def test_personalization_parser_intents(text: str, intent: IntentType) -> None:
    result = CommandParser().parse(text)
    assert result.matched
    assert result.command.intent is intent


def test_parser_extracts_preference_entities() -> None:
    parsed = CommandParser().parse("Set my preferred browser to Chrome")
    values = {item.name: item.value for item in parsed.command.entities}
    assert values == {
        "preference_key": "default_browser",
        "preference_value": "Chrome",
    }


def test_parser_normalizes_quiet_hours() -> None:
    parsed = CommandParser().parse("Enable quiet hours from 10 PM to 7 AM")
    values = {item.name: item.value for item in parsed.command.entities}
    assert values["preference_value"] == "22:00-07:00"


def test_parser_preserves_voice_source() -> None:
    parsed = CommandParser().parse("Use concise responses", source=CommandSource.VOICE)
    assert parsed.command.source is CommandSource.VOICE
