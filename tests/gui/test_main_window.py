"""Headless tests for Version 2 main-window structure."""

from __future__ import annotations

import inspect
from datetime import UTC, datetime

from omega.gui.dialogs import about_text
from omega.gui.main_window import OmegaMainWindow
from omega.gui.models import ConversationMessage, GuiPreferences, MessageKind


class AnyController:
    def __getattr__(self, _name: str):
        return lambda: None


def test_about_text_contains_product_branding_and_safety_guidance() -> None:
    content = about_text("Hello Omega")
    assert "Omega Windows Assistant\nVersion 2.0.0" in content
    assert "Developed by Anshuman Pattanayak" in content
    assert "A safety-first, local-first Windows desktop assistant." in content
    assert "https://github.com/ItsAnshumanPattanayak/Omega-Windows-Assistant" in content
    assert 'Activate with "Hello Omega"' in content
    assert "safety gateway" in content


def test_controller_is_initialized_before_widget_build() -> None:
    source = inspect.getsource(OmegaMainWindow.__init__)

    assert source.index("self.controller = GuiController") < source.index(
        "self._build()"
    )


def test_more_activities_preserves_every_secondary_action_category() -> None:
    window = object.__new__(OmegaMainWindow)
    window.controller = AnyController()  # type: ignore[assignment]

    groups = window._activity_action_groups()
    labels = {label for actions in groups.values() for label, _command in actions}

    assert set(groups) == {
        "Applications and browser",
        "Productivity",
        "Scheduling",
        "Knowledge",
        "Email and calendar",
        "Workflows",
        "Plugins and local AI",
        "System and privacy",
    }
    assert {
        "Open browser",
        "Show history",
        "Reminders",
        "Collections",
        "Email status",
        "Calendar",
        "List workflows",
        "Plugins",
        "Local AI status",
        "Clipboard",
        "Screenshot",
        "My profile",
        "Help / About",
    } <= labels
    assert len(labels) == 61


def test_activity_panel_toggles_without_duplicate_windows() -> None:
    calls: list[tuple[str, object]] = []

    class Panes:
        def forget(self, child: object) -> None:
            calls.append(("forget", child))

        def add(self, child: object, *, weight: int) -> None:
            calls.append(("add", (child, weight)))

    class Button:
        def configure(self, **values: object) -> None:
            calls.append(("button", values["text"]))

    window = object.__new__(OmegaMainWindow)
    window.panes = Panes()  # type: ignore[assignment]
    window.activity_frame = object()  # type: ignore[assignment]
    window.activity_toggle_button = Button()  # type: ignore[assignment]
    window._activity_visible = True

    window._toggle_activity()
    window._toggle_activity()

    assert calls[0][0] == "forget"
    assert calls[1] == ("button", "Show activity")
    assert calls[2][0] == "add"
    assert calls[3] == ("button", "Hide activity")
    assert window._activity_visible


def test_chat_messages_use_directional_alignment_and_remain_selectable() -> None:
    insertions: list[tuple[object, ...]] = []

    class Conversation:
        def configure(self, **_values: object) -> None:
            return None

        def insert(self, *values: object) -> None:
            insertions.append(values)

        def see(self, _index: str) -> None:
            return None

    window = object.__new__(OmegaMainWindow)
    window.conversation = Conversation()  # type: ignore[assignment]
    window.preferences = GuiPreferences()
    now = datetime.now(UTC)

    window.add_message(ConversationMessage("You", "Hello", MessageKind.USER, now))
    window.add_message(ConversationMessage("Omega", "Hi", MessageKind.ASSISTANT, now))

    user_tags = insertions[0][2]
    assistant_tags = insertions[2][2]
    assert "message_user" in user_tags
    assert "message_assistant" in assistant_tags
