from __future__ import annotations

from pathlib import Path

import pytest

from omega.accessibility import (
    AccessibilityConfiguration,
    AccessibilityFeature,
    AccessibilityService,
    AiTranslationDraft,
    FakeAccessibleGuiState,
    KeyboardShortcut,
    KeyboardShortcutRegistry,
    RecordingAccessibilityEventSink,
    destructive_confirmation_default_focus,
    multilingual_confirmation_allowed,
    select_sapi_voice,
    voice_language_status,
)
from omega.core.exceptions import (
    AccessibilityConfigurationError,
    AccessibilityError,
    LanguagePackValidationError,
)
from omega.gui.models import GuiPreferences


def test_accessibility_disabled_ignores_updates() -> None:
    service = AccessibilityService(AccessibilityConfiguration(enabled=False))
    assert service.update(high_contrast_enabled=True).high_contrast_enabled is False


def test_accessibility_updates_and_events() -> None:
    sink = RecordingAccessibilityEventSink()
    service = AccessibilityService(AccessibilityConfiguration(), event_sink=sink)
    settings = service.update(
        font_scale=1.5,
        high_contrast_enabled=True,
        reduced_motion_enabled=True,
        terminal_color_enabled=False,
        terminal_screen_reader_mode=True,
    )
    assert settings.font_scale == 1.5
    assert settings.high_contrast_enabled and settings.reduced_motion_enabled
    assert sink.events[-1].feature is AccessibilityFeature.TERMINAL_ACCESSIBILITY


@pytest.mark.parametrize("scale", [0.79, 2.01])
def test_font_scale_bounds(scale: float) -> None:
    with pytest.raises(AccessibilityConfigurationError):
        AccessibilityService(AccessibilityConfiguration()).update(font_scale=scale)


def test_bounded_confirmation_timeout_cannot_remove_confirmation() -> None:
    service = AccessibilityService(
        AccessibilityConfiguration(maximum_confirmation_timeout_multiplier=3.0)
    )
    service.update(confirmation_timeout_multiplier=2.5)
    assert service.confirmation_timeout(30) == 75
    assert service.confirmation_timeout(200) == 300
    with pytest.raises(AccessibilityConfigurationError):
        service.confirmation_timeout(0)
    with pytest.raises(AccessibilityConfigurationError):
        service.update(confirmation_timeout_multiplier=0.0)


def test_screen_reader_terminal_uses_textual_state() -> None:
    service = AccessibilityService(AccessibilityConfiguration())
    assert (
        service.terminal_message("error", "Could not open item")
        == "Error: Could not open item"
    )


def test_keyboard_shortcuts_register_without_confirmation_bypass() -> None:
    calls: list[str] = []
    registry = KeyboardShortcutRegistry()
    registry.register(
        KeyboardShortcut("Ctrl+L", "Focus command input"), lambda: calls.append("focus")
    )
    assert registry.invoke("ctrl+l") is True
    assert calls == ["focus"]
    assert registry.invoke("ctrl+l", confirmation_pending=True) is False
    assert registry.descriptions() == ("Ctrl+L: Focus command input",)
    with pytest.raises(AccessibilityError):
        KeyboardShortcut("Enter", "Approve", safety_bypass=True)


def test_focus_restoration_and_non_color_status() -> None:
    gui = FakeAccessibleGuiState()
    gui.open_dialog("cancel_button")
    assert gui.focus == "cancel_button"
    assert (
        gui.announce("warning", "Confirmation expires in 30 seconds")
        == "Warning: Confirmation expires in 30 seconds"
    )
    gui.close_dialog()
    assert gui.focus == "command_input"
    assert destructive_confirmation_default_focus() == "cancel"


def test_gui_preferences_validate_accessibility_values() -> None:
    value = GuiPreferences.from_values(
        {"font_scale": 1.75, "high_contrast": True, "screen_reader_friendly": True}
    )
    assert value.font_scale == 1.75
    assert value.high_contrast and value.screen_reader_friendly
    assert GuiPreferences.from_values({"font_scale": 10}).font_scale == 1.0


def test_voice_model_language_status_and_text_fallback() -> None:
    missing = voice_language_status("hi", None)
    assert missing.recognition_reliable is False
    assert "text mode" in str(missing.warning)
    assert voice_language_status("hi", Path("vosk-model-hi-0.22")).recognition_reliable
    mismatch = voice_language_status("hi", Path("vosk-model-en-us"))
    assert mismatch.recognition_reliable is False
    assert mismatch.warning is not None


def test_sapi_fallback_and_voice_confidence() -> None:
    assert select_sapi_voice("Missing", ("Voice A",)) is None
    assert select_sapi_voice(None, ("Voice A",)) == "Voice A"
    assert multilingual_confirmation_allowed(0.85, 0.85)
    assert not multilingual_confirmation_allowed(0.84, 0.85)


def test_ai_translation_draft_stays_unverified_and_critical_is_blocked() -> None:
    draft = AiTranslationDraft("app.ready", "Ready", "तैयार")
    assert draft.verified is False
    assert draft.approve().verified is True
    with pytest.raises(LanguagePackValidationError):
        AiTranslationDraft(
            "confirmation.destructive", "Delete?", "हटाएँ?", critical=True
        ).approve()
