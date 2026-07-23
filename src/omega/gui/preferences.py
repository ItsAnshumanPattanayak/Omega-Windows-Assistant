"""Safe mutable GUI preferences backed by Phase 10 runtime settings."""

from __future__ import annotations

from dataclasses import asdict

from omega.database import RuntimeSettingsRepository
from omega.gui.models import GuiPreferences

_PREFIX = "ui."


class GuiPreferencesService:
    """Load and save only allowlisted JSON-compatible UI preferences."""

    _FIELDS = frozenset(asdict(GuiPreferences()))

    def __init__(self, repository: RuntimeSettingsRepository) -> None:
        self.repository = repository

    def load(self) -> GuiPreferences:
        values: dict[str, object] = {}
        for name in self._FIELDS:
            setting = self.repository.get(_PREFIX + name)
            if setting is not None:
                values[name] = setting.value
        return GuiPreferences.from_values(values)

    def save(self, preferences: GuiPreferences) -> GuiPreferences:
        validated = GuiPreferences.from_values(asdict(preferences))
        for name, value in asdict(validated).items():
            self.repository.upsert(_PREFIX + name, value)
        return validated
