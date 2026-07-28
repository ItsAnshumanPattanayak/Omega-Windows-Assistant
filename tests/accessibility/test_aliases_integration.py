from __future__ import annotations

from uuid import uuid4

import pytest

from omega.accessibility import (
    CommandAliasCatalog,
    LocalizationConfiguration,
    create_default_aliases,
)
from omega.core.exceptions import LanguagePackValidationError
from omega.models import IntentType
from omega.personalization import (
    FakePreferenceRepository,
    PersonalizationConfiguration,
    PreferenceResolver,
    PreferenceService,
    PreferenceValidator,
)
from omega.understanding import CommandParser


@pytest.mark.parametrize(
    "text,intent",
    [
        ("Change language to English", IntentType.SET_PREFERENCE),
        ("Change language to Hindi", IntentType.SET_PREFERENCE),
        ("Use 24-hour time", IntentType.SET_PREFERENCE),
        ("Enable high contrast", IntentType.SET_PREFERENCE),
        ("Increase text size", IntentType.SET_PREFERENCE),
        ("Decrease text size", IntentType.SET_PREFERENCE),
        ("Enable screen-reader mode", IntentType.SET_PREFERENCE),
        ("Disable terminal colors", IntentType.SET_PREFERENCE),
        ("Show keyboard shortcuts", IntentType.SET_PREFERENCE),
        ("Speak more slowly", IntentType.SET_PREFERENCE),
        ("Use concise spoken responses", IntentType.SET_PREFERENCE),
        ("Show accessibility settings", IntentType.SHOW_PREFERENCES),
        ("Reset accessibility settings", IntentType.RESET_PREFERENCE_CATEGORY),
    ],
)
def test_accessibility_parser_intents(text: str, intent: IntentType) -> None:
    parsed = CommandParser().parse(text)
    assert parsed.command.intent is intent
    assert parsed.matched is True


@pytest.mark.parametrize(
    "text,key,value",
    [
        ("Change language to English", "language", "en"),
        ("Change language to Hindi", "language", "hi"),
        ("Enable high contrast", "high_contrast", True),
        ("Increase text size", "font_scaling", 1.25),
        ("Decrease text size", "font_scaling", 0.9),
        ("Enable screen-reader mode", "screen_reader_friendly_mode", True),
        ("Disable terminal colors", "terminal_color_enabled", False),
        ("Use concise spoken responses", "spoken_response_mode", "concise"),
    ],
)
def test_accessibility_entity_extraction(text: str, key: str, value: object) -> None:
    entities = {
        item.name: item.value for item in CommandParser().parse(text).command.entities
    }
    assert entities["preference_key"] == key
    assert entities["preference_value"] == value


@pytest.mark.parametrize(
    "text,intent",
    [
        ("मदद", IntentType.HELP),
        ("सुलभता सेटिंग्स दिखाएँ", IntentType.SHOW_PREFERENCES),
        ("भाषा हिंदी करें", IntentType.SET_PREFERENCE),
        ("उच्च कंट्रास्ट सक्षम करें", IntentType.SET_PREFERENCE),
    ],
)
def test_hindi_aliases(text: str, intent: IntentType) -> None:
    parsed = CommandParser(language="hi").parse(text)
    assert parsed.command.intent is intent


def test_english_alias_remains_available_with_hindi_active() -> None:
    assert CommandParser(language="hi").parse("help").command.intent is IntentType.HELP


def test_alias_catalog_rejects_ambiguity_and_excess() -> None:
    catalog = CommandAliasCatalog(
        LocalizationConfiguration(maximum_command_aliases_per_intent=1)
    )
    catalog.register("en", IntentType.HELP, ("assist",))
    with pytest.raises(LanguagePackValidationError):
        catalog.register("en", IntentType.SHOW_HISTORY, ("assist",))
    with pytest.raises(LanguagePackValidationError):
        catalog.register("en", IntentType.HELP, ("one", "two"))


def test_hidden_character_in_sensitive_alias_requires_clarification() -> None:
    catalog = create_default_aliases()
    catalog.register("en", IntentType.DELETE_FILE, ("delete selected file",))
    parsed = CommandParser(command_aliases=catalog).parse("delete\u200b selected file")
    assert parsed.requires_clarification is True
    assert parsed.command.confidence == 0.0


def test_unicode_titles_remain_exact_data() -> None:
    for title in ("नोट 📝", "Tâche café", "कैलेंडर बैठक", "कार्यप्रवाह ✓"):
        parsed = CommandParser().parse(f"create a note named {title}")
        assert title in parsed.command.original_text


def test_preference_precedence_and_session_expiration() -> None:
    repository = FakePreferenceRepository()
    resolver = PreferenceResolver(repository, {"language": "en"})
    service = PreferenceService(
        PersonalizationConfiguration(),
        repository,
        PreferenceValidator(PersonalizationConfiguration()),
        resolver,
    )
    service.set_preference("language", "hi")
    session_id = uuid4()
    service.set_preference("language", "en", session_id=session_id, temporary=True)
    assert resolver.resolve("language", session_id=session_id).value == "en"
    resolver.clear_session(session_id)
    assert resolver.resolve("language", session_id=session_id).value == "hi"


def test_safety_preferences_still_dominate() -> None:
    repository = FakePreferenceRepository()
    resolver = PreferenceResolver(repository)
    assert resolver.resolve("mandatory_confirmations").value is True
