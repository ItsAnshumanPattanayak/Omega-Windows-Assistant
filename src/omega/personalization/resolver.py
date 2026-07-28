"""Deterministic preference precedence with mandatory safety dominance."""

from __future__ import annotations

from collections.abc import Mapping
from uuid import UUID

from omega.models._serialization import JsonValue
from omega.personalization.definitions import DEFINITION_MAP, SAFETY_VALUES
from omega.personalization.exceptions import PreferenceValidationError
from omega.personalization.models import PreferenceSource, ResolvedPreference
from omega.personalization.repository import PreferenceRepository


class PreferenceResolver:
    def __init__(
        self,
        repository: PreferenceRepository,
        configuration_values: Mapping[str, JsonValue] | None = None,
    ) -> None:
        self.repository = repository
        self.configuration_values = dict(configuration_values or {})
        self._session: dict[UUID, dict[str, JsonValue]] = {}

    def resolve(
        self, key: str, *, session_id: UUID | None = None, profile_id: str | None = None
    ) -> ResolvedPreference:
        definition = DEFINITION_MAP.get(key)
        if definition is None:
            raise PreferenceValidationError("That preference is unsupported.")
        if key in SAFETY_VALUES:
            return ResolvedPreference(
                key, SAFETY_VALUES[key], PreferenceSource.SAFETY_POLICY, True
            )
        if session_id is not None and key in self._session.get(session_id, {}):
            return ResolvedPreference(
                key, self._session[session_id][key], PreferenceSource.SESSION_OVERRIDE
            )
        owner = profile_id or self.repository.active_profile_id()
        if owner is not None:
            stored = {
                item.key: item.value for item in self.repository.list_preferences(owner)
            }
            if key in stored:
                return ResolvedPreference(
                    key, stored[key], PreferenceSource.ACTIVE_PROFILE
                )
        if key in self.configuration_values:
            return ResolvedPreference(
                key,
                self.configuration_values[key],
                PreferenceSource.APPLICATION_CONFIGURATION,
            )
        return ResolvedPreference(
            key, definition.default, PreferenceSource.BUILT_IN_DEFAULT
        )

    def set_session(self, session_id: UUID, key: str, value: JsonValue) -> None:
        self._session.setdefault(session_id, {})[key] = value

    def clear_session(self, session_id: UUID) -> None:
        self._session.pop(session_id, None)

    def clear_all_sessions(self) -> None:
        """Invalidate temporary selections when the active profile changes."""

        self._session.clear()

    def clear_session_key(self, session_id: UUID, key: str) -> None:
        values = self._session.get(session_id)
        if values is not None:
            values.pop(key, None)

    def session_values(self, session_id: UUID) -> dict[str, JsonValue]:
        return dict(self._session.get(session_id, {}))
