"""Public privacy-first accessibility and localization API."""

from omega.accessibility.aliases import (
    AliasMatch,
    CommandAliasCatalog,
    create_default_aliases,
)
from omega.accessibility.catalog import LanguagePackValidator, TranslationCatalog
from omega.accessibility.configuration import (
    AccessibilityConfiguration,
    LocalizationConfiguration,
)
from omega.accessibility.formatting import (
    DateTimeFormatter,
    LocaleFormatter,
    NumberFormatter,
)
from omega.accessibility.gui import (
    FakeAccessibleGuiState,
    KeyboardShortcut,
    KeyboardShortcutRegistry,
    destructive_confirmation_default_focus,
)
from omega.accessibility.integrations import (
    AiTranslationDraft,
    PluginLocalizationRegistry,
)
from omega.accessibility.localization import (
    LanguagePackRegistry,
    LocalizationService,
    create_default_localization,
)
from omega.accessibility.models import (
    AccessibilityEvent,
    AccessibilityFeature,
    AccessibilitySettings,
    AccessibilityState,
    LanguageIdentifier,
    LanguagePackDescriptor,
    LocaleIdentifier,
    LocalizedMessage,
    MessageKey,
    TextDirection,
)
from omega.accessibility.service import (
    AccessibilityEventSink,
    AccessibilityService,
    RecordingAccessibilityEventSink,
)
from omega.accessibility.text import (
    NormalizedText,
    normalize_command_text,
    terminal_safe_text,
)
from omega.accessibility.voice import (
    VoiceAccessibilityStatus,
    multilingual_confirmation_allowed,
    select_sapi_voice,
    voice_language_status,
)

__all__ = [
    "AccessibilityConfiguration",
    "AccessibilityEvent",
    "AccessibilityEventSink",
    "AccessibilityFeature",
    "AccessibilityService",
    "AccessibilitySettings",
    "AccessibilityState",
    "AiTranslationDraft",
    "AliasMatch",
    "CommandAliasCatalog",
    "DateTimeFormatter",
    "FakeAccessibleGuiState",
    "KeyboardShortcut",
    "KeyboardShortcutRegistry",
    "LanguageIdentifier",
    "LanguagePackDescriptor",
    "LanguagePackRegistry",
    "LanguagePackValidator",
    "LocaleFormatter",
    "LocaleIdentifier",
    "LocalizationConfiguration",
    "LocalizationService",
    "LocalizedMessage",
    "MessageKey",
    "NormalizedText",
    "NumberFormatter",
    "PluginLocalizationRegistry",
    "RecordingAccessibilityEventSink",
    "TextDirection",
    "TranslationCatalog",
    "VoiceAccessibilityStatus",
    "create_default_aliases",
    "create_default_localization",
    "destructive_confirmation_default_focus",
    "multilingual_confirmation_allowed",
    "normalize_command_text",
    "select_sapi_voice",
    "terminal_safe_text",
    "voice_language_status",
]
