from pathlib import Path

import pytest

from omega.core.exceptions import SettingsRepositoryError
from omega.database import (
    DatabaseConfiguration,
    DatabaseConnectionFactory,
    MigrationRunner,
    RuntimeSettingsRepository,
)
from omega.gui.models import GuiPreferences
from omega.gui.preferences import GuiPreferencesService


def _service(tmp_path: Path):
    factory = DatabaseConnectionFactory(
        DatabaseConfiguration(), database_path=tmp_path / "omega.db"
    )
    MigrationRunner(factory).migrate()
    repository = RuntimeSettingsRepository(factory)
    return GuiPreferencesService(repository), repository


def test_safe_preferences_round_trip(tmp_path: Path):
    service, _ = _service(tmp_path)
    expected = GuiPreferences(
        theme="dark",
        font_size=14,
        history_limit=30,
        auto_scroll=False,
        notifications_enabled=False,
    )

    assert service.save(expected) == expected
    assert service.load() == expected


def test_malformed_preferences_fall_back_safely(tmp_path: Path):
    service, repository = _service(tmp_path)
    repository.upsert("ui.theme", "malicious")
    repository.upsert("ui.font_size", 999)
    repository.upsert("ui.window_width", -1)

    loaded = service.load()

    assert loaded.theme == "system"
    assert loaded.font_size == 11
    assert loaded.window_width == 1100


def test_reserved_safety_setting_remains_immutable(tmp_path: Path):
    _, repository = _service(tmp_path)

    with pytest.raises(SettingsRepositoryError, match="immutable"):
        repository.upsert("safety.default_decision", "allow")
