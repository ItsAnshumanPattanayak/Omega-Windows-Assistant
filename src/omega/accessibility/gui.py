"""Headless accessibility policies for GUI focus and keyboard interaction."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from omega.core.exceptions import AccessibilityError


@dataclass(frozen=True, slots=True)
class KeyboardShortcut:
    key: str
    description: str
    safety_bypass: bool = False

    def __post_init__(self) -> None:
        if not self.key.strip() or not self.description.strip():
            raise AccessibilityError("Keyboard shortcut labels must be non-empty.")
        if self.safety_bypass:
            raise AccessibilityError("Keyboard shortcuts cannot bypass confirmation.")


class KeyboardShortcutRegistry:
    def __init__(self) -> None:
        self._shortcuts: dict[str, tuple[KeyboardShortcut, Callable[[], None]]] = {}

    def register(
        self, shortcut: KeyboardShortcut, callback: Callable[[], None]
    ) -> None:
        normalized = shortcut.key.casefold()
        if normalized in self._shortcuts:
            raise AccessibilityError(
                "Keyboard shortcut conflicts with an existing one."
            )
        self._shortcuts[normalized] = (shortcut, callback)

    def invoke(self, key: str, *, confirmation_pending: bool = False) -> bool:
        registered = self._shortcuts.get(key.casefold())
        if registered is None or confirmation_pending:
            return False
        registered[1]()
        return True

    def descriptions(self) -> tuple[str, ...]:
        return tuple(
            f"{item.key}: {item.description}" for item, _ in self._shortcuts.values()
        )


class FakeAccessibleGuiState:
    """Display-free focus/status adapter used by controller and smoke tests."""

    def __init__(self, initial_focus: str = "command_input") -> None:
        self.focus = initial_focus
        self._previous_focus: str | None = None
        self.status = "Ready"

    def open_dialog(self, dialog_focus: str) -> None:
        if not dialog_focus.strip():
            raise AccessibilityError("Dialog focus target must be labelled.")
        self._previous_focus, self.focus = self.focus, dialog_focus

    def close_dialog(self) -> None:
        self.focus = self._previous_focus or "command_input"
        self._previous_focus = None

    def announce(self, state: str, detail: str) -> str:
        if not state.strip() or not detail.strip():
            raise AccessibilityError("Status announcements require text.")
        self.status = f"{state.title()}: {detail}"
        return self.status


def destructive_confirmation_default_focus() -> str:
    return "cancel"
