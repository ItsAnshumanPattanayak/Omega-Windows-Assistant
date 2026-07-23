"""Immutable display models with no dependency on tkinter."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class MessageKind(StrEnum):
    """Visual and semantic category for conversation text."""

    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"
    SUCCESS = "success"
    WARNING = "warning"
    ERROR = "error"


class GuiStatus(StrEnum):
    """High-level state shown by the desktop status bar."""

    READY = "ready"
    PROCESSING = "processing"
    AWAITING_CONFIRMATION = "awaiting_confirmation"
    ERROR = "error"
    CLOSED = "closed"


@dataclass(frozen=True)
class ConversationMessage:
    """One safe, selectable conversation entry."""

    sender: str
    text: str
    kind: MessageKind
    occurred_at: datetime


@dataclass(frozen=True)
class ActivityItem:
    """One bounded persistent-history row suitable for display."""

    identifier: str
    kind: str
    summary: str
    status: str
    timestamp: str


@dataclass(frozen=True)
class UndoAvailability:
    """Safe display state for the latest unconsumed recovery record."""

    available: bool
    description: str


@dataclass(frozen=True)
class ConfirmationRequest:
    """Exact existing confirmation phrases for one pending action."""

    prompt: str
    display_target: str
    confirmation_phrase: str
    cancellation_phrase: str


@dataclass(frozen=True)
class Notification:
    """A non-sensitive in-application notification."""

    title: str
    message: str
    kind: MessageKind


@dataclass(frozen=True)
class GuiPreferences:
    """Validated mutable desktop preferences."""

    theme: str = "system"
    font_size: int = 11
    history_limit: int = 20
    auto_scroll: bool = True
    notifications_enabled: bool = True
    speak_responses: bool = True
    window_width: int = 1100
    window_height: int = 720
    maximized: bool = False

    @classmethod
    def from_values(cls, values: dict[str, object]) -> GuiPreferences:
        """Load safe values, falling back per malformed preference."""

        defaults = cls()
        theme = values.get("theme", defaults.theme)
        if theme not in {"system", "light", "dark"}:
            theme = defaults.theme
        font_size = cls._bounded_int(values.get("font_size"), defaults.font_size, 9, 24)
        history_limit = cls._bounded_int(
            values.get("history_limit"), defaults.history_limit, 1, 100
        )
        width = cls._bounded_int(
            values.get("window_width"), defaults.window_width, 760, 3840
        )
        height = cls._bounded_int(
            values.get("window_height"), defaults.window_height, 520, 2160
        )
        return cls(
            theme=str(theme),
            font_size=font_size,
            history_limit=history_limit,
            auto_scroll=cls._boolean(values.get("auto_scroll"), defaults.auto_scroll),
            notifications_enabled=cls._boolean(
                values.get("notifications_enabled"),
                defaults.notifications_enabled,
            ),
            speak_responses=cls._boolean(
                values.get("speak_responses"),
                defaults.speak_responses,
            ),
            window_width=width,
            window_height=height,
            maximized=cls._boolean(values.get("maximized"), defaults.maximized),
        )

    @staticmethod
    def _bounded_int(value: object, default: int, minimum: int, maximum: int) -> int:
        if isinstance(value, bool) or not isinstance(value, int):
            return default
        return value if minimum <= value <= maximum else default

    @staticmethod
    def _boolean(value: object, default: bool) -> bool:
        return value if isinstance(value, bool) else default
