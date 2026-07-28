"""Serializable personalization models containing no service logic."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from uuid import uuid4

from omega.models._serialization import JsonValue, serialize_value, utc_now
from omega.personalization.exceptions import PreferenceValidationError

_IDENTIFIER = re.compile(r"^[a-z][a-z0-9_.-]{0,99}$")


class PreferenceCategory(StrEnum):
    GENERAL = "general"
    APPLICATIONS = "applications"
    FILES_FOLDERS = "files_folders"
    VOICE = "voice"
    GUI = "gui"
    NOTIFICATIONS = "notifications"
    EMAIL = "email"
    CALENDAR = "calendar"
    LOCAL_AI = "local_ai"
    WORKFLOWS = "workflows"
    ACCESSIBILITY = "accessibility"
    PRIVACY = "privacy"
    PLUGIN = "plugin"


class PreferenceScope(StrEnum):
    SESSION = "session"
    PROFILE = "profile"
    PLUGIN = "plugin"


class PreferenceSource(StrEnum):
    SAFETY_POLICY = "safety_policy"
    SESSION_OVERRIDE = "session_override"
    ACTIVE_PROFILE = "active_profile"
    LOCAL_PERSISTED = "local_persisted"
    APPLICATION_CONFIGURATION = "application_configuration"
    BUILT_IN_DEFAULT = "built_in_default"


@dataclass(frozen=True)
class PreferenceDefinition:
    key: str
    category: PreferenceCategory
    value_type: str
    default: JsonValue
    choices: tuple[JsonValue, ...] = ()
    sensitive: bool = False
    workflow_accessible: bool = False
    plugin_readable: bool = False

    def __post_init__(self) -> None:
        if not _IDENTIFIER.fullmatch(self.key):
            raise PreferenceValidationError("The preference key is invalid.")
        if self.value_type not in {
            "string",
            "boolean",
            "integer",
            "number",
            "time_range",
        }:
            raise PreferenceValidationError("The preference value type is invalid.")


@dataclass(frozen=True)
class UserProfile:
    name: str
    profile_id: str = field(default_factory=lambda: uuid4().hex)
    is_default: bool = False
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)

    def to_dict(self) -> dict[str, JsonValue]:
        return {
            "profile_id": self.profile_id,
            "name": self.name,
            "is_default": self.is_default,
            "created_at": serialize_value(self.created_at),
            "updated_at": serialize_value(self.updated_at),
        }


@dataclass(frozen=True)
class UserPreference:
    profile_id: str
    key: str
    value: JsonValue
    category: PreferenceCategory
    scope: PreferenceScope = PreferenceScope.PROFILE
    source: PreferenceSource = PreferenceSource.LOCAL_PERSISTED
    updated_at: datetime = field(default_factory=utc_now)

    def to_dict(self) -> dict[str, JsonValue]:
        return {
            "profile_id": self.profile_id,
            "key": self.key,
            "value": serialize_value(self.value),
            "category": self.category.value,
            "scope": self.scope.value,
            "source": self.source.value,
            "updated_at": serialize_value(self.updated_at),
        }


@dataclass(frozen=True)
class ResolvedPreference:
    key: str
    value: JsonValue
    source: PreferenceSource
    safety_override: bool = False


@dataclass(frozen=True)
class PreferenceValidationResult:
    valid: bool
    normalized_value: JsonValue | None = None
    errors: tuple[str, ...] = ()


@dataclass(frozen=True)
class PreferenceChangeResult:
    changed: bool
    message: str
    key: str | None = None
    category: PreferenceCategory | None = None


@dataclass(frozen=True)
class PreferenceEvent:
    event_type: str
    profile_id: str
    category: PreferenceCategory | None
    occurred_at: datetime = field(default_factory=utc_now)


@dataclass(frozen=True)
class ProfileImportPreview:
    profile_name: str
    preferences: tuple[tuple[str, JsonValue], ...]
    schema_version: int
    preview_id: str = field(default_factory=lambda: uuid4().hex)

    def summary(self) -> str:
        return (
            f"Profile {self.profile_name}: "
            f"{len(self.preferences)} validated preference(s)."
        )
