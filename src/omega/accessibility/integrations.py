"""Narrow plugin and local-AI localization integration boundaries."""

from __future__ import annotations

from dataclasses import dataclass

from omega.accessibility.catalog import LanguagePackValidator, TranslationCatalog
from omega.accessibility.models import LanguagePackDescriptor
from omega.core.exceptions import LanguagePackValidationError


class PluginLocalizationRegistry:
    def __init__(self, validator: LanguagePackValidator) -> None:
        self.validator = validator
        self._catalogs: dict[tuple[str, str], TranslationCatalog] = {}

    def register(
        self,
        plugin_id: str,
        descriptor: LanguagePackDescriptor,
        entries: dict[str, object],
        *,
        permission_granted: bool,
    ) -> TranslationCatalog:
        if not permission_granted:
            raise LanguagePackValidationError(
                "Plugin localization registration is not approved."
            )
        catalog = self.validator.validate(
            descriptor, entries, plugin_namespace=plugin_id
        )
        self._catalogs[(plugin_id, descriptor.language.value)] = catalog
        return catalog


@dataclass(frozen=True, slots=True)
class AiTranslationDraft:
    message_key: str
    source_text: str
    translated_text: str
    verified: bool = False
    critical: bool = False

    def approve(self) -> AiTranslationDraft:
        if self.critical:
            raise LanguagePackValidationError(
                "AI drafts cannot replace critical confirmation translations."
            )
        return AiTranslationDraft(
            self.message_key,
            self.source_text,
            self.translated_text,
            verified=True,
            critical=False,
        )
