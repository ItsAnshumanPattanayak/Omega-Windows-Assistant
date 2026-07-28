"""Offline localization registry and reliable English fallback service."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import replace

from omega.accessibility.catalog import (
    ENGLISH_MESSAGES,
    HINDI_PREVIEW_MESSAGES,
    LanguagePackValidator,
    TranslationCatalog,
)
from omega.accessibility.configuration import LocalizationConfiguration
from omega.accessibility.models import (
    LanguageIdentifier,
    LanguagePackDescriptor,
    LocaleIdentifier,
    LocalizedMessage,
    MessageKey,
)
from omega.core.exceptions import LanguagePackValidationError

_CRITICAL_PREFIXES = ("confirmation.",)


class LanguagePackRegistry:
    def __init__(self) -> None:
        self._catalogs: dict[str, TranslationCatalog] = {}

    def register(self, catalog: TranslationCatalog) -> None:
        code = catalog.descriptor.language.value
        if code in self._catalogs:
            raise LanguagePackValidationError("Language pack is already registered.")
        self._catalogs[code] = catalog

    def get(self, language: str) -> TranslationCatalog | None:
        return self._catalogs.get(language)

    def descriptors(self) -> tuple[LanguagePackDescriptor, ...]:
        return tuple(item.descriptor for item in self._catalogs.values())


class LocalizationService:
    """Render trusted catalog templates without network access or dynamic evaluation."""

    def __init__(
        self,
        configuration: LocalizationConfiguration,
        registry: LanguagePackRegistry,
        *,
        active_language: str | None = None,
    ) -> None:
        self.configuration = configuration
        self.registry = registry
        self.active_language = active_language or configuration.default_language

    def set_language(self, language: str) -> None:
        LanguageIdentifier(language)
        if self.registry.get(language) is None:
            raise LanguagePackValidationError("Language pack is not installed.")
        self.active_language = language

    def message(self, key: str, **values: object) -> LocalizedMessage:
        message_key = MessageKey(key)
        requested = self.active_language if self.configuration.enabled else "en"
        selected = self.registry.get(requested)
        base = self.registry.get(self.configuration.fallback_language)
        template: str | None = None
        language = requested
        used_fallback = False
        if selected is not None and not (
            key.startswith(_CRITICAL_PREFIXES) and selected.descriptor.coverage < 1.0
        ):
            template = selected.entries.get(key)
        if template is None and base is not None:
            template = base.entries.get(key)
            language = base.descriptor.language.value
            used_fallback = language != requested
        if template is None:
            return LocalizedMessage(message_key, key, LanguageIdentifier("en"), True)
        try:
            rendered = template.format_map(_StrictValues(values))
        except (KeyError, ValueError):
            if base is selected or base is None or key not in base.entries:
                return LocalizedMessage(
                    message_key, key, LanguageIdentifier("en"), True
                )
            try:
                rendered = base.entries[key].format_map(_StrictValues(values))
            except (KeyError, ValueError):
                return LocalizedMessage(
                    message_key, key, LanguageIdentifier("en"), True
                )
            language, used_fallback = "en", True
        return LocalizedMessage(
            message_key, rendered, LanguageIdentifier(language), used_fallback
        )


class _StrictValues(dict[str, object]):
    def __init__(self, values: Mapping[str, object]) -> None:
        super().__init__(values)

    def __missing__(self, key: str) -> object:
        raise KeyError(key)


def create_default_localization(
    configuration: LocalizationConfiguration | None = None,
) -> LocalizationService:
    config = configuration or LocalizationConfiguration()
    validator = LanguagePackValidator(config)
    registry = LanguagePackRegistry()
    english = validator.validate(
        LanguagePackDescriptor(
            "English", LanguageIdentifier("en"), LocaleIdentifier("en_US"), "1.0.0"
        ),
        ENGLISH_MESSAGES,
    )
    registry.register(english)
    preview_validator = LanguagePackValidator(
        replace(config, allow_partial_language_packs=True)
    )
    hindi = preview_validator.validate(
        LanguagePackDescriptor(
            "हिन्दी (पूर्वावलोकन)",
            LanguageIdentifier("hi"),
            LocaleIdentifier("hi_IN"),
            "1.0.0",
            coverage=len(HINDI_PREVIEW_MESSAGES) / len(ENGLISH_MESSAGES),
            fallback_language=LanguageIdentifier("en"),
            preview=True,
        ),
        HINDI_PREVIEW_MESSAGES,
        base_catalog=english,
    )
    registry.register(hindi)
    return LocalizationService(config, registry)
