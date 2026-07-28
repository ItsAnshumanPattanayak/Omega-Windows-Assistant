"""Bounded, data-only translation catalogs with strict placeholder validation."""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from string import Formatter
from types import MappingProxyType
from typing import Any

from omega.accessibility.configuration import LocalizationConfiguration
from omega.accessibility.models import LanguagePackDescriptor, MessageKey
from omega.core.exceptions import LanguagePackValidationError, SecurityValidationError
from omega.security import JsonSecurityLimits, load_bounded_json

_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_EXECUTABLE = re.compile(
    r"(?:\beval\s*\(|\bexec\s*\(|<script\b|javascript:|powershell\s+-|cmd\s+/c)",
    re.IGNORECASE,
)


def _placeholders(template: str) -> frozenset[str]:
    try:
        fields = {
            name
            for _, name, format_spec, conversion in Formatter().parse(template)
            if name is not None
            and not format_spec
            and conversion is None
            and name.isidentifier()
        }
        parsed_count = sum(
            1 for _, name, _, _ in Formatter().parse(template) if name is not None
        )
    except ValueError as error:
        raise LanguagePackValidationError(
            "Translation template braces are invalid."
        ) from error
    if len(fields) != parsed_count:
        raise LanguagePackValidationError(
            "Only simple named translation placeholders are allowed."
        )
    return frozenset(fields)


@dataclass(frozen=True, slots=True)
class TranslationCatalog:
    descriptor: LanguagePackDescriptor
    entries: Mapping[str, str]

    def __post_init__(self) -> None:
        object.__setattr__(self, "entries", MappingProxyType(dict(self.entries)))

    def canonical_bytes(self) -> bytes:
        return json.dumps(
            dict(self.entries),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")

    def fingerprint(self) -> str:
        return self.descriptor.fingerprint(self.canonical_bytes())


class LanguagePackValidator:
    """Validate catalog shape, size, text, and source-placeholder parity."""

    def __init__(self, configuration: LocalizationConfiguration) -> None:
        self.configuration = configuration

    def validate(
        self,
        descriptor: LanguagePackDescriptor,
        entries: Mapping[str, object],
        *,
        base_catalog: TranslationCatalog | None = None,
        plugin_namespace: str | None = None,
    ) -> TranslationCatalog:
        if len(entries) > self.configuration.maximum_catalog_entries:
            raise LanguagePackValidationError(
                "Translation catalog has too many entries."
            )
        clean: dict[str, str] = {}
        for key, value in entries.items():
            MessageKey(key)
            if plugin_namespace is not None and not key.startswith(
                f"plugin.{plugin_namespace}."
            ):
                raise LanguagePackValidationError(
                    "Plugin translations must remain in their own namespace."
                )
            if not isinstance(value, str) or not value:
                raise LanguagePackValidationError(
                    "Translation values must be non-empty plain text."
                )
            if len(value) > self.configuration.maximum_message_characters:
                raise LanguagePackValidationError("Translation message is too large.")
            if _CONTROL.search(value):
                raise LanguagePackValidationError(
                    "Translation contains prohibited control characters."
                )
            if _EXECUTABLE.search(value):
                raise LanguagePackValidationError(
                    "Executable translation content is prohibited."
                )
            placeholders = _placeholders(value)
            if base_catalog is not None and key in base_catalog.entries:
                expected = _placeholders(base_catalog.entries[key])
                if placeholders != expected:
                    raise LanguagePackValidationError(
                        f"Translation placeholders do not match source key {key}."
                    )
            clean[key] = value
        catalog = TranslationCatalog(descriptor, clean)
        if len(catalog.canonical_bytes()) > self.configuration.maximum_catalog_bytes:
            raise LanguagePackValidationError("Translation catalog is too large.")
        if (
            descriptor.coverage < 1.0
            and not self.configuration.allow_partial_language_packs
        ):
            raise LanguagePackValidationError("Partial language packs are disabled.")
        return catalog

    def load_json(
        self,
        path: Path,
        descriptor: LanguagePackDescriptor,
        *,
        root: Path,
        base_catalog: TranslationCatalog | None = None,
    ) -> TranslationCatalog:
        resolved_root = root.resolve(strict=False)
        resolved = path.resolve(strict=False)
        try:
            resolved.relative_to(resolved_root)
        except ValueError as error:
            raise LanguagePackValidationError(
                "Language-pack path must remain in the approved directory."
            ) from error
        try:
            size = resolved.stat().st_size
            if size > self.configuration.maximum_catalog_bytes:
                raise LanguagePackValidationError("Translation catalog is too large.")
            raw: Any = load_bounded_json(
                resolved.read_bytes(),
                JsonSecurityLimits(
                    self.configuration.maximum_catalog_bytes,
                    maximum_depth=3,
                    maximum_items=self.configuration.maximum_catalog_entries * 2,
                ),
            )
        except LanguagePackValidationError:
            raise
        except (OSError, SecurityValidationError) as error:
            raise LanguagePackValidationError(
                "Translation catalog could not be read safely."
            ) from error
        if not isinstance(raw, dict):
            raise LanguagePackValidationError("Translation catalog must be an object.")
        return self.validate(descriptor, raw, base_catalog=base_catalog)


ENGLISH_MESSAGES: dict[str, str] = {
    "app.ready": "Omega is ready.",
    "app.activate": 'Say "{activation_phrase}" to activate.',
    "app.greeting": (
        "{period}, {display_name}. How's your day going? How can I help you?"
    ),
    "command.success": "Success: {message}",
    "command.error": "Error: {message}",
    "command.warning": "Warning: {message}",
    "command.received": "I received your command.",
    "confirmation.destructive": (
        "{action} {target}? This is destructive. Choose Yes or Cancel."
    ),
    "confirmation.external": (
        "{action} {target}? This affects an external service. Choose Yes or Cancel."
    ),
    "status.enabled": "Enabled",
    "status.disabled": "Disabled",
    "status.error": "Error",
    "status.warning": "Warning",
    "status.success": "Success",
    "accessibility.settings": "Accessibility settings",
    "accessibility.shortcuts": "Keyboard shortcuts",
    "accessibility.reset": "Reset accessibility settings",
    "voice.unavailable": (
        "The configured voice is unavailable; text mode remains available."
    ),
    "knowledge.results": "Knowledge search results",
    "email.draft_review": "Email draft review",
    "calendar.proposal": "Calendar proposal",
    "workflow.status": "Workflow status",
    "plugin.status": "Plugin status",
    "ai.status": "Local AI status",
    "personalization.settings": "Personalization settings",
}

HINDI_PREVIEW_MESSAGES: dict[str, str] = {
    "app.ready": "ओमेगा तैयार है।",
    "app.activate": 'सक्रिय करने के लिए "{activation_phrase}" कहें।',
    "app.greeting": "{period}, {display_name}। आपका दिन कैसा चल रहा है? मैं कैसे मदद करूँ?",
    "command.success": "सफल: {message}",
    "command.error": "त्रुटि: {message}",
    "command.warning": "चेतावनी: {message}",
    "accessibility.settings": "सुलभता सेटिंग्स",
    "accessibility.shortcuts": "कीबोर्ड शॉर्टकट",
    "status.enabled": "सक्षम",
    "status.disabled": "अक्षम",
}
