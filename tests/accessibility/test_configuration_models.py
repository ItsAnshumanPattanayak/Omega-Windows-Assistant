from __future__ import annotations

import pytest

from omega.accessibility import (
    AccessibilityConfiguration,
    AccessibilityFeature,
    AccessibilitySettings,
    AccessibilityState,
    LanguageIdentifier,
    LanguagePackDescriptor,
    LocaleIdentifier,
    LocalizationConfiguration,
    MessageKey,
    TextDirection,
)
from omega.core.exceptions import (
    AccessibilityConfigurationError,
    LanguagePackValidationError,
)


def test_accessibility_defaults_are_conservative() -> None:
    value = AccessibilityConfiguration()
    assert value.enabled is True
    assert value.keyboard_navigation_enabled is True
    assert value.font_scale == 1.0
    assert value.confirmation_timeout_multiplier == 1.0


def test_localization_defaults_are_local_only() -> None:
    value = LocalizationConfiguration()
    assert value.default_language == "en"
    assert value.fallback_language == "en"
    assert value.allow_external_translation_services is False
    assert value.automatically_download_language_packs is False


@pytest.mark.parametrize(
    "values",
    [
        {"unknown": True},
        {"font_scale": 0.5},
        {"minimum_font_scale": 2.0, "maximum_font_scale": 1.0},
        {"confirmation_timeout_multiplier": 0.5},
        {"spoken_response_mode": "unbounded"},
        {"enabled": "yes"},
    ],
)
def test_accessibility_configuration_rejects_invalid(values: dict[str, object]) -> None:
    with pytest.raises(AccessibilityConfigurationError):
        AccessibilityConfiguration.from_mapping(values)


@pytest.mark.parametrize(
    "values",
    [
        {"unknown": True},
        {"default_language": "../../en"},
        {"default_locale": "invalid locale"},
        {"maximum_catalog_entries": 0},
        {"maximum_command_aliases_per_intent": 101},
        {"allow_external_translation_services": True},
        {"automatically_download_language_packs": True},
    ],
)
def test_localization_configuration_rejects_invalid(values: dict[str, object]) -> None:
    with pytest.raises(AccessibilityConfigurationError):
        LocalizationConfiguration.from_mapping(values)


@pytest.mark.parametrize("value", ["en", "hi", "en-US"])
def test_language_identifiers(value: str) -> None:
    assert str(LanguageIdentifier(value)) == value


@pytest.mark.parametrize("value", ["en_US", "hi_IN", "en"])
def test_locale_identifiers(value: str) -> None:
    assert str(LocaleIdentifier(value)) == value


@pytest.mark.parametrize("value", ["../en", "EN", "english", "e"])
def test_invalid_language_identifiers(value: str) -> None:
    with pytest.raises(LanguagePackValidationError):
        LanguageIdentifier(value)


def test_model_enums_and_message_key() -> None:
    assert AccessibilityFeature.FONT_SCALING.value == "font_scaling"
    assert AccessibilityState.ENABLED.value == "enabled"
    assert TextDirection.RIGHT_TO_LEFT.value == "rtl"
    assert str(MessageKey("app.ready")) == "app.ready"
    assert AccessibilitySettings().terminal_color_enabled is True


def test_descriptor_requires_partial_pack_to_be_preview() -> None:
    with pytest.raises(LanguagePackValidationError):
        LanguagePackDescriptor(
            "Partial",
            LanguageIdentifier("hi"),
            LocaleIdentifier("hi_IN"),
            "1.0.0",
            coverage=0.5,
        )


def test_descriptor_validates_api_and_versions() -> None:
    with pytest.raises(LanguagePackValidationError):
        LanguagePackDescriptor(
            "Hindi",
            LanguageIdentifier("hi"),
            LocaleIdentifier("hi_IN"),
            "v1",
        )
    with pytest.raises(LanguagePackValidationError):
        LanguagePackDescriptor(
            "Hindi",
            LanguageIdentifier("hi"),
            LocaleIdentifier("hi_IN"),
            "1.0.0",
            api_version="2.0",
        )
