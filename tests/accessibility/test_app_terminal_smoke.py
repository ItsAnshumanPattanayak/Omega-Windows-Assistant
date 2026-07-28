from __future__ import annotations

from datetime import UTC, datetime

from omega.accessibility import (
    AccessibilityConfiguration,
    AccessibilityService,
    FakeAccessibleGuiState,
    KeyboardShortcut,
    KeyboardShortcutRegistry,
    LocaleFormatter,
    create_default_aliases,
    create_default_localization,
)
from omega.interfaces.terminal import TerminalInterface
from omega.models import IntentType
from omega.session import OmegaSession
from omega.understanding import CommandParser


def _session(parser: CommandParser | None = None) -> OmegaSession:
    return OmegaSession(
        {"display_name": "Anshuman"},
        {
            "activation_phrase": "Hello Omega",
            "shutdown_phrase": "Shut down Omega",
            "active_session_timeout_seconds": 300,
        },
        parser=parser,
    )


def test_localized_terminal_startup_and_clean_shutdown() -> None:
    localization = create_default_localization()
    localization.set_language("hi")
    outputs: list[str] = []
    interface = TerminalInterface(
        _session(),
        localization=localization,
        accessibility=AccessibilityService(AccessibilityConfiguration()),
        input_func=lambda _prompt: "Shut down Omega",
        output_func=outputs.append,
    )
    assert interface.run() == 0
    assert outputs[0] == "ओमेगा तैयार है।"
    assert outputs[-1].startswith("Omega:")


def test_phase_25_fake_smoke_has_no_side_effects() -> None:
    localization = create_default_localization()
    assert localization.registry.get("en") is not None
    assert localization.registry.get("hi") is not None
    localization.set_language("hi")
    assert localization.message("app.ready").language.value == "hi"
    assert localization.message("knowledge.results").language.value == "en"

    formatted = LocaleFormatter(
        "hi_IN", time_format="24-hour", date_format="day-first", time_zone="UTC"
    )
    now = datetime(2026, 7, 28, 10, 30, tzinfo=UTC)
    assert formatted.format_date(now) == "28/07/2026"
    assert formatted.format_time(now) == "10:30 UTC"

    aliases = create_default_aliases()
    safe = aliases.match("मदद", "hi")
    assert safe is not None and safe.intent is IntentType.HELP
    aliases.register("hi", IntentType.DELETE_FILE, ("चयनित फ़ाइल हटाएँ",))
    destructive = aliases.match("चयनित फ़ाइल हटाएँ", "hi")
    assert destructive is not None and destructive.intent is IntentType.DELETE_FILE

    accessibility = AccessibilityService(AccessibilityConfiguration())
    accessibility.update(
        terminal_screen_reader_mode=True,
        terminal_color_enabled=False,
        font_scale=1.4,
        high_contrast_enabled=True,
    )
    assert accessibility.settings.terminal_screen_reader_mode is True

    shortcuts = KeyboardShortcutRegistry()
    calls: list[str] = []
    shortcuts.register(
        KeyboardShortcut("Ctrl+L", "Focus input"), lambda: calls.append("focus")
    )
    assert shortcuts.invoke("Ctrl+L", confirmation_pending=True) is False
    gui = FakeAccessibleGuiState()
    gui.open_dialog("cancel")
    gui.close_dialog()
    assert gui.focus == "command_input"

    session_id = _session().session_id
    assert session_id is None
    assert calls == []
    # Fake services performed no network, provider, shell, email, calendar, file,
    # screenshot, clipboard, workflow, plugin, or AI action.


def test_localization_disabled_uses_english() -> None:
    from omega.accessibility import LocalizationConfiguration

    localization = create_default_localization(LocalizationConfiguration(enabled=False))
    localization.set_language("hi")
    assert localization.message("app.ready").text == "Omega is ready."
