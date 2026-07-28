"""Bounded JSON profile export, preview, and confirmed import."""

from __future__ import annotations

import json
from typing import Any

from omega.core.exceptions import SecurityValidationError
from omega.personalization.configuration import PersonalizationConfiguration
from omega.personalization.definitions import DEFINITION_MAP
from omega.personalization.exceptions import (
    PreferenceValidationError,
    ProfileTransferError,
)
from omega.personalization.models import ProfileImportPreview
from omega.personalization.service import PreferenceService
from omega.security import JsonSecurityLimits, load_bounded_json

PROFILE_SCHEMA_VERSION = 1
_PROHIBITED_FIELDS = {
    "password",
    "token",
    "credential",
    "private_key",
    "email_body",
    "clipboard",
    "screenshot",
    "document_content",
    "ai_prompt",
    "ai_response",
}


class ProfileExportService:
    def __init__(
        self, service: PreferenceService, configuration: PersonalizationConfiguration
    ) -> None:
        self.service = service
        self.configuration = configuration

    def export_json(self) -> str:
        profile = self.service.active_profile
        values = {
            item.key: item.value
            for item in self.service.list_preferences()
            if item.key in DEFINITION_MAP and not DEFINITION_MAP[item.key].sensitive
        }
        payload = {
            "schema_version": PROFILE_SCHEMA_VERSION,
            "profile": {"name": profile.name},
            "preferences": values,
            "privacy": {
                "contains_credentials": False,
                "contains_private_content": False,
            },
        }
        encoded = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)
        if len(encoded.encode("utf-8")) > self.configuration.maximum_export_bytes:
            raise ProfileTransferError("The profile export is too large.")
        return encoded


class ProfileImportService:
    def __init__(
        self, service: PreferenceService, configuration: PersonalizationConfiguration
    ) -> None:
        self.service = service
        self.configuration = configuration
        self._previews: dict[str, ProfileImportPreview] = {}

    def preview(self, raw: str | bytes) -> ProfileImportPreview:
        data = raw.encode("utf-8") if isinstance(raw, str) else raw
        if len(data) > self.configuration.maximum_export_bytes:
            raise ProfileTransferError("The profile import is too large.")
        try:
            value = load_bounded_json(
                data,
                JsonSecurityLimits(
                    self.configuration.maximum_export_bytes,
                    maximum_depth=8,
                    maximum_items=len(DEFINITION_MAP) * 4,
                ),
            )
        except SecurityValidationError as error:
            raise ProfileTransferError(
                "The profile import is not valid JSON."
            ) from error
        if not isinstance(value, dict) or set(value) - {
            "schema_version",
            "profile",
            "preferences",
            "privacy",
        }:
            raise ProfileTransferError(
                "The profile import contains unsupported fields."
            )
        if value.get("schema_version") != PROFILE_SCHEMA_VERSION:
            raise ProfileTransferError("The profile schema is unsupported.")
        profile = value.get("profile")
        preferences = value.get("preferences")
        if (
            not isinstance(profile, dict)
            or set(profile) != {"name"}
            or not isinstance(preferences, dict)
        ):
            raise ProfileTransferError("The profile import structure is invalid.")
        lowered = {str(key).casefold() for key in preferences}
        if any(
            any(prohibited in key for prohibited in _PROHIBITED_FIELDS)
            for key in lowered
        ):
            raise ProfileTransferError(
                "The profile import contains prohibited private fields."
            )
        validated: list[tuple[str, Any]] = []
        for key, candidate in preferences.items():
            if not isinstance(key, str) or key not in DEFINITION_MAP:
                raise ProfileTransferError(
                    "The profile import contains an unsupported preference."
                )
            try:
                normalized = self.service.validator.require(key, candidate)
            except PreferenceValidationError as error:
                raise ProfileTransferError(
                    "The profile import contains an invalid preference."
                ) from error
            validated.append((key, normalized))
        preview = ProfileImportPreview(
            str(profile["name"]), tuple(validated), PROFILE_SCHEMA_VERSION
        )
        self._previews[preview.preview_id] = preview
        return preview

    def apply(self, preview_id: str, *, confirmed: bool = False) -> int:
        preview = self._previews.pop(preview_id, None)
        if preview is None:
            raise ProfileTransferError("The import preview is stale or unavailable.")
        if self.configuration.require_confirmation_for_profile_import and not confirmed:
            raise ProfileTransferError("Profile import requires confirmation.")
        for key, value in preview.preferences:
            self.service.set_preference(key, value)
        return len(preview.preferences)
