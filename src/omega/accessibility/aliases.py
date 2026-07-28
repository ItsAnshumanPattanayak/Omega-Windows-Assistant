"""Language-aware aliases mapped only to existing Omega intents."""

from __future__ import annotations

from dataclasses import dataclass

from omega.accessibility.configuration import LocalizationConfiguration
from omega.accessibility.models import LanguageIdentifier
from omega.accessibility.text import normalize_command_text
from omega.core.exceptions import LanguagePackValidationError, UnicodeSafetyError
from omega.models import IntentType

_DESTRUCTIVE = frozenset(
    {
        IntentType.DELETE_FILE,
        IntentType.DELETE_FOLDER,
        IntentType.DELETE_CALENDAR_EVENT,
        IntentType.RESET_ALL_PREFERENCES,
    }
)


@dataclass(frozen=True, slots=True)
class AliasMatch:
    intent: IntentType
    language: LanguageIdentifier
    requires_clarification: bool = False
    confidence: float = 1.0


class CommandAliasCatalog:
    def __init__(self, configuration: LocalizationConfiguration) -> None:
        self.configuration = configuration
        self._aliases: dict[str, dict[str, IntentType]] = {}

    def register(
        self, language: str, intent: IntentType, aliases: tuple[str, ...]
    ) -> None:
        LanguageIdentifier(language)
        if len(aliases) > self.configuration.maximum_command_aliases_per_intent:
            raise LanguagePackValidationError("Too many aliases for one intent.")
        catalog = self._aliases.setdefault(language, {})
        for alias in aliases:
            try:
                key = normalize_command_text(
                    alias, safety_sensitive=intent in _DESTRUCTIVE
                )
            except UnicodeSafetyError as error:
                raise LanguagePackValidationError("Command alias is unsafe.") from error
            if not key.text or key.safety_ambiguous:
                raise LanguagePackValidationError("Command alias is unsafe or empty.")
            existing = catalog.get(key.text)
            if existing is not None and existing is not intent:
                raise LanguagePackValidationError("Command alias is ambiguous.")
            catalog[key.text] = intent

    def match(self, text: str, language: str = "en") -> AliasMatch | None:
        normalized = normalize_command_text(text)
        for code in (language, "en") if language != "en" else ("en",):
            intent = self._aliases.get(code, {}).get(normalized.text)
            if intent is None:
                continue
            unsafe = intent in _DESTRUCTIVE and normalized.removed_zero_width
            return AliasMatch(
                intent,
                LanguageIdentifier(code),
                requires_clarification=unsafe,
                confidence=0.0 if unsafe else 1.0,
            )
        return None


def create_default_aliases(
    configuration: LocalizationConfiguration | None = None,
) -> CommandAliasCatalog:
    config = configuration or LocalizationConfiguration()
    catalog = CommandAliasCatalog(config)
    english: dict[IntentType, tuple[str, ...]] = {
        IntentType.HELP: ("help", "show help"),
        IntentType.SHOW_PREFERENCES: ("show accessibility settings",),
        IntentType.RESET_PREFERENCE_CATEGORY: ("reset accessibility settings",),
        IntentType.SET_PREFERENCE: (
            "change language to english",
            "change language to hindi",
            "use 24-hour time",
            "enable high contrast",
            "increase text size",
            "decrease text size",
            "enable screen-reader mode",
            "disable terminal colors",
            "show keyboard shortcuts",
            "speak more slowly",
            "use concise spoken responses",
        ),
    }
    hindi: dict[IntentType, tuple[str, ...]] = {
        IntentType.HELP: ("मदद", "सहायता दिखाएँ"),
        IntentType.SHOW_PREFERENCES: ("सुलभता सेटिंग्स दिखाएँ",),
        IntentType.SET_PREFERENCE: (
            "भाषा अंग्रेज़ी करें",
            "भाषा हिंदी करें",
            "उच्च कंट्रास्ट सक्षम करें",
            "टेक्स्ट का आकार बढ़ाएँ",
        ),
    }
    for intent, aliases in english.items():
        catalog.register("en", intent, aliases)
    for intent, aliases in hindi.items():
        catalog.register("hi", intent, aliases)
    return catalog
