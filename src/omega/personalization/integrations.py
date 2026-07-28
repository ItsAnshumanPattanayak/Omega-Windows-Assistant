"""Narrow plugin, workflow, formatting, greeting, and AI preference views."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, time
from uuid import UUID

from omega.models._serialization import JsonValue
from omega.personalization.definitions import DEFINITION_MAP
from omega.personalization.exceptions import (
    PreferencePermissionError,
    PreferenceValidationError,
)
from omega.personalization.resolver import PreferenceResolver
from omega.personalization.service import PreferenceService


class PluginPreferenceAccess:
    def __init__(
        self,
        resolver: PreferenceResolver,
        permission_check: Callable[[str, str, str, str], None],
    ) -> None:
        self.resolver = resolver
        self.permission_check = permission_check
        self._plugin_values: dict[str, dict[str, JsonValue]] = {}

    def read(
        self, plugin_id: str, version: str, fingerprint: str, key: str
    ) -> JsonValue:
        self.permission_check(
            plugin_id, version, fingerprint, "read_non_sensitive_preferences"
        )
        definition = DEFINITION_MAP.get(key)
        if definition is None or not definition.plugin_readable or definition.sensitive:
            raise PreferencePermissionError("The plugin cannot read that preference.")
        return self.resolver.resolve(key).value

    def write_own(
        self,
        plugin_id: str,
        version: str,
        fingerprint: str,
        key: str,
        value: JsonValue,
    ) -> None:
        self.permission_check(
            plugin_id, version, fingerprint, "write_plugin_preferences"
        )
        if not key.startswith(plugin_id + "."):
            raise PreferencePermissionError(
                "Plugins may write only their own namespace."
            )
        self._plugin_values.setdefault(plugin_id, {})[key] = value


class WorkflowPreferenceAccess:
    def __init__(
        self, resolver: PreferenceResolver, service: PreferenceService
    ) -> None:
        self.resolver = resolver
        self.service = service

    def resolve(self, key: str, *, session_id: UUID | None = None) -> JsonValue:
        definition = DEFINITION_MAP.get(key)
        if definition is None or not definition.workflow_accessible:
            raise PreferencePermissionError(
                "That preference is not available to workflows."
            )
        value = self.resolver.resolve(key, session_id=session_id).value
        self.service.validator.require(key, value)
        return value


class PersonalizationContext:
    """Provide one explicitly requested preference rather than a whole profile."""

    def __init__(self, resolver: PreferenceResolver) -> None:
        self.resolver = resolver

    def for_ai(
        self, key: str, *, session_id: UUID | None = None
    ) -> dict[str, JsonValue]:
        allowed = {
            "language",
            "response_verbosity",
            "ai_response_length",
            "ai_grounded_answers",
        }
        if key not in allowed:
            raise PreferenceValidationError(
                "That preference is not available to local AI."
            )
        return {key: self.resolver.resolve(key, session_id=session_id).value}

    def format_response(
        self,
        text: str,
        *,
        session_id: UUID | None = None,
        safety_critical: bool = False,
    ) -> str:
        if safety_critical:
            return text
        style = self.resolver.resolve("response_verbosity", session_id=session_id).value
        if style == "concise":
            first = text.splitlines()[0].strip()
            return first[:500]
        if style == "detailed":
            return (
                text + "\n\nDetails are shown without changing the underlying result."
            )
        return text

    def greeting(self, fallback_name: str, current_time: datetime) -> str:
        preferred = self.resolver.resolve("display_name").value
        name = preferred if isinstance(preferred, str) and preferred else fallback_name
        if not self.resolver.resolve("greeting_enabled").value:
            return f"Omega is active, {name}."
        if 5 <= current_time.hour < 12:
            salutation = "Good morning"
        elif 12 <= current_time.hour < 17:
            salutation = "Good afternoon"
        else:
            salutation = "Good evening"
        if self.resolver.resolve("greeting_style").value == "brief":
            return f"{salutation}, {name}."
        return f"{salutation}, {name}. How's your day going? How can I help you?"

    def is_quiet_time(self, current_time: time) -> bool:
        return self._in_range(self.resolver.resolve("quiet_hours").value, current_time)

    def is_working_time(self, current_time: time) -> bool:
        return self._in_range(
            self.resolver.resolve("working_hours").value, current_time
        )

    @staticmethod
    def _in_range(raw: JsonValue, current_time: time) -> bool:
        if not isinstance(raw, str) or not raw:
            return False
        start_text, end_text = raw.split("-", 1)
        start = time.fromisoformat(start_text)
        end = time.fromisoformat(end_text)
        if start <= end:
            return start <= current_time < end
        return current_time >= start or current_time < end
