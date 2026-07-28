"""Strict validation for explicit, non-sensitive preference values."""

from __future__ import annotations

import re
from collections.abc import Iterable
from pathlib import PurePath
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from omega.models._serialization import JsonValue
from omega.personalization.configuration import PersonalizationConfiguration
from omega.personalization.definitions import DEFINITION_MAP
from omega.personalization.exceptions import PreferenceValidationError
from omega.personalization.models import (
    PreferenceDefinition,
    PreferenceValidationResult,
)

_CONTROL = re.compile(r"[\x00-\x1f\x7f]")
_EXECUTABLE = re.compile(
    r"(?:^|\s)(?:powershell|cmd(?:\.exe)?|python|wscript|cscript|bash|sh)(?:\s|$)|"
    r"(?:^|\s)(?:eval|exec)\s*\(|[;&|`]",
    re.IGNORECASE,
)
_SECRET = re.compile(
    r"(?:password|passwd|api[_ -]?key|auth(?:entication)?[_ -]?token|private[_ -]?key|"
    r"bearer\s+[a-z0-9._-]+)",
    re.IGNORECASE,
)
_LANGUAGE = re.compile(r"^[a-z]{2,3}(?:-[A-Z]{2})?$")
_LOCALE = re.compile(r"^[a-z]{2,3}(?:[-_][A-Z]{2})?(?:\.[A-Za-z0-9-]+)?$")
_ALIAS = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 _.-]{0,79}$")
_TIME_RANGE = re.compile(r"^(?:[01]\d|2[0-3]):[0-5]\d-(?:[01]\d|2[0-3]):[0-5]\d$")


class PreferenceValidator:
    def __init__(
        self,
        configuration: PersonalizationConfiguration,
        *,
        application_aliases: Iterable[str] = (),
        folder_aliases: Iterable[str] = (
            "desktop",
            "documents",
            "downloads",
            "pictures",
            "project",
            "workspace",
            "exports",
            "screenshots",
        ),
    ) -> None:
        self.configuration = configuration
        self.application_aliases = {item.casefold() for item in application_aliases}
        self.folder_aliases = {item.casefold() for item in folder_aliases}

    def validate(self, key: str, value: object) -> PreferenceValidationResult:
        definition = DEFINITION_MAP.get(key)
        if definition is None:
            return PreferenceValidationResult(
                False, errors=("That preference is unsupported.",)
            )
        try:
            normalized = self._normalize(definition, value)
            return PreferenceValidationResult(True, normalized)
        except PreferenceValidationError as error:
            return PreferenceValidationResult(False, errors=(str(error),))

    def require(self, key: str, value: object) -> JsonValue:
        result = self.validate(key, value)
        if not result.valid:
            raise PreferenceValidationError(result.errors[0])
        return result.normalized_value

    def _normalize(self, definition: PreferenceDefinition, value: object) -> JsonValue:
        kind = definition.value_type
        if kind == "boolean":
            if not isinstance(value, bool):
                raise PreferenceValidationError(
                    "The preference requires true or false."
                )
            normalized: JsonValue = value
        elif kind == "integer":
            if isinstance(value, bool) or not isinstance(value, int):
                raise PreferenceValidationError(
                    "The preference requires a whole number."
                )
            normalized = value
        elif kind == "number":
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise PreferenceValidationError("The preference requires a number.")
            normalized = float(value)
        elif kind in {"string", "time_range"}:
            if not isinstance(value, str):
                raise PreferenceValidationError("The preference requires text.")
            normalized = value.strip()
            self._safe_text(normalized)
        else:
            raise PreferenceValidationError("The preference type is unsupported.")
        self._specialized(definition, normalized)
        return normalized

    def _safe_text(self, value: str) -> None:
        if len(value) > self.configuration.maximum_preference_value_characters:
            raise PreferenceValidationError("The preference value is too large.")
        if _CONTROL.search(value):
            raise PreferenceValidationError("Control characters are not allowed.")
        if _EXECUTABLE.search(value):
            raise PreferenceValidationError("Executable content is not allowed.")
        if _SECRET.search(value):
            raise PreferenceValidationError("Secrets cannot be stored as preferences.")

    def _specialized(self, definition: PreferenceDefinition, value: JsonValue) -> None:
        key = definition.key
        if definition.choices and value not in definition.choices:
            raise PreferenceValidationError("The preference value is not supported.")
        if (
            key == "display_name"
            and isinstance(value, str)
            and len(value) > self.configuration.maximum_display_name_characters
        ):
            raise PreferenceValidationError("The display name is too long.")
        if (
            key in {"language", "voice_language"}
            and isinstance(value, str)
            and not _LANGUAGE.fullmatch(value)
        ):
            raise PreferenceValidationError("The language code is invalid.")
        if key == "locale" and isinstance(value, str) and not _LOCALE.fullmatch(value):
            raise PreferenceValidationError("The locale identifier is invalid.")
        if key == "wake_word_aliases" and isinstance(value, str):
            aliases = tuple(part.strip() for part in value.split(",") if part.strip())
            if len(aliases) > 10 or any(len(alias) > 80 for alias in aliases):
                raise PreferenceValidationError("Wake-word aliases exceed safe bounds.")
        if key == "time_zone" and value != "system":
            try:
                ZoneInfo(str(value))
            except (ZoneInfoNotFoundError, ValueError) as error:
                raise PreferenceValidationError(
                    "The time-zone identifier is invalid."
                ) from error
        if (
            definition.value_type == "time_range"
            and value
            and not _TIME_RANGE.fullmatch(str(value))
        ):
            raise PreferenceValidationError("Use a 24-hour range such as 22:00-07:00.")
        if (
            key
            in {
                "default_browser",
                "default_editor",
                "preferred_terminal",
                "preferred_media_player",
            }
            and value
        ):
            if not _ALIAS.fullmatch(str(value)) or (
                self.application_aliases
                and str(value).casefold() not in self.application_aliases
            ):
                raise PreferenceValidationError(
                    "The application alias is not registered."
                )
        if key.endswith("folder_alias") or key == "workspace_alias":
            text = str(value)
            if text and (
                PurePath(text).is_absolute()
                or ".." in PurePath(text).parts
                or text.casefold() not in self.folder_aliases
            ):
                raise PreferenceValidationError(
                    "The folder preference must use an approved alias."
                )
        bounds = {
            "speech_rate": (80, 400),
            "speech_volume": (0.0, 1.0),
            "font_scaling": (0.75, 2.0),
            "confirmation_timeout_seconds": (15, 300),
            "maximum_notifications": (1, 100),
            "default_event_duration_minutes": (5, 1440),
            "calendar_reminder_minutes": (0, 10080),
            "ai_maximum_context_turns": (1, 20),
            "workflow_history_length": (0, 1000),
            "workflow_timeout_seconds": (1, 3600),
        }
        if key in bounds:
            minimum, maximum = bounds[key]
            if (
                not isinstance(value, (int, float))
                or isinstance(value, bool)
                or not minimum <= value <= maximum
            ):
                raise PreferenceValidationError(
                    "The numeric preference is outside its safe bounds."
                )
