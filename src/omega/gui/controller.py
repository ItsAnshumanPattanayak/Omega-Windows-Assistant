"""Headless GUI controller coordinating existing production services."""

from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol

from omega.core.exceptions import GuiTaskError, OmegaError
from omega.gui.formatting import format_activity
from omega.gui.models import (
    ActivityItem,
    ConfirmationRequest,
    ConversationMessage,
    GuiPreferences,
    GuiStatus,
    MessageKind,
    Notification,
    UndoAvailability,
)
from omega.gui.preferences import GuiPreferencesService
from omega.gui.task_runner import GuiTaskRunner
from omega.history import HistoryService
from omega.safety import SafeExecutionGateway
from omega.session import OmegaSession

MAX_COMMAND_CHARACTERS = 10_000


class GuiView(Protocol):
    """UI operations used by the controller and implemented on the Tk thread."""

    def add_message(self, message: ConversationMessage) -> None: ...

    def set_status(self, status: GuiStatus, detail: str) -> None: ...

    def set_busy(self, busy: bool) -> None: ...

    def show_activity(self, items: Sequence[ActivityItem]) -> None: ...

    def set_undo_availability(self, availability: UndoAvailability) -> None: ...

    def show_confirmation(self, request: ConfirmationRequest) -> None: ...

    def dismiss_confirmation(self) -> None: ...

    def notify(self, notification: Notification) -> None: ...

    def apply_preferences(self, preferences: GuiPreferences) -> None: ...

    def update_session_state(self, state: str) -> None: ...


@dataclass(frozen=True)
class _CommandOutcome:
    response: str
    activity: _ActivitySnapshot
    activity_error: bool
    confirmation: ConfirmationRequest | None
    session_state: str


@dataclass(frozen=True)
class _ActivitySnapshot:
    items: tuple[ActivityItem, ...]
    undo: UndoAvailability


class GuiController:
    """Submit each GUI command exactly once through ``OmegaSession``."""

    def __init__(
        self,
        session: OmegaSession,
        history: HistoryService,
        preferences: GuiPreferencesService,
        gateway: SafeExecutionGateway,
        runner: GuiTaskRunner,
        view: GuiView,
        *,
        logger: logging.Logger | None = None,
    ) -> None:
        self.session = session
        self.history = history
        self.preferences = preferences
        self.gateway = gateway
        self.runner = runner
        self.view = view
        self.logger = logger or logging.getLogger("omega.gui.controller")
        self._busy = False
        self._pending: ConfirmationRequest | None = None
        self._preferences = GuiPreferences()

    @property
    def busy(self) -> bool:
        return self._busy

    @property
    def current_preferences(self) -> GuiPreferences:
        return self._preferences

    def start(self) -> None:
        """Load preferences and activity without blocking the UI thread."""

        self.view.update_session_state(self.session.state.value)
        self.refresh_activity()
        self.runner.submit(
            self.preferences.load,
            self._preferences_loaded,
            self._task_error,
        )

    def submit_command(self, text: str) -> bool:
        """Validate and schedule one exact session command."""

        if self._busy:
            self._notify(
                "Omega is busy",
                "Wait for the current operation to finish.",
                MessageKind.WARNING,
            )
            return False
        if not isinstance(text, str) or not text.strip():
            self._notify(
                "Command required",
                "Enter a command before sending.",
                MessageKind.WARNING,
            )
            return False
        if len(text) > MAX_COMMAND_CHARACTERS:
            self._notify(
                "Command too long",
                f"Commands are limited to {MAX_COMMAND_CHARACTERS:,} characters.",
                MessageKind.ERROR,
            )
            return False

        self.view.add_message(
            ConversationMessage("You", text, MessageKind.USER, datetime.now(UTC))
        )
        self._set_busy(True)
        try:
            self.runner.submit(
                lambda: self._process_command(text),
                self._command_completed,
                self._command_failed,
            )
        except GuiTaskError as error:
            self._command_failed(error)
            return False
        return True

    def activate(self) -> bool:
        return self.submit_command(self.session.activation_phrase)

    def shutdown_session(self) -> bool:
        return self.submit_command(self.session.shutdown_phrase)

    def show_history(self) -> bool:
        return self.submit_command("show history")

    def request_undo(self) -> bool:
        return self.submit_command("undo last action")

    def export_history(self) -> bool:
        return self.submit_command("export history")

    def clear_history(self) -> bool:
        return self.submit_command("clear history")

    def confirm_pending(self) -> bool:
        """Route the current exact confirmation phrase through the session."""

        if self._pending is None:
            self._notify(
                "No confirmation",
                "There is no pending operation to confirm.",
                MessageKind.WARNING,
            )
            return False
        return self.submit_command(self._pending.confirmation_phrase)

    def cancel_pending(self) -> bool:
        """Route cancellation through the same scoped confirmation path."""

        if self._pending is None:
            self.view.dismiss_confirmation()
            return False
        return self.submit_command(self._pending.cancellation_phrase)

    def refresh_activity(self) -> bool:
        if self._busy:
            return False
        self._set_busy(True, "Refreshing history")
        try:
            self.runner.submit(
                self._load_activity,
                self._activity_loaded,
                self._command_failed,
            )
        except GuiTaskError as error:
            self._command_failed(error)
            return False
        return True

    def save_preferences(self, preferences: GuiPreferences) -> bool:
        if self._busy:
            return False
        self._set_busy(True, "Saving settings")
        try:
            self.runner.submit(
                lambda: self.preferences.save(preferences),
                self._preferences_saved,
                self._command_failed,
            )
        except GuiTaskError as error:
            self._command_failed(error)
            return False
        return True

    def close(self) -> None:
        """Cancel confirmation safely and close worker resources."""

        self._pending = None
        self.runner.shutdown(wait=True)
        self.session.interrupt()
        self.view.set_status(GuiStatus.CLOSED, "Closed")

    def _process_command(self, text: str) -> _CommandOutcome:
        response = self.session.handle_input(text)
        activity_error = False
        try:
            activity = self._load_activity()
        except OmegaError:
            self.logger.exception("GUI activity refresh failed after a command.")
            activity = _ActivitySnapshot(
                (),
                UndoAvailability(False, "Undo state is unavailable."),
            )
            activity_error = True
        pending = None
        session_id = self.session.session_id
        if session_id is not None:
            existing = self.gateway.confirmations.get(session_id)
            if existing is not None:
                pending = ConfirmationRequest(
                    existing.prompt,
                    existing.display_target,
                    existing.expected_confirmation,
                    existing.expected_cancellation,
                )
        return _CommandOutcome(
            response,
            activity,
            activity_error,
            pending,
            self.session.state.value,
        )

    def _load_activity(self) -> _ActivitySnapshot:
        limit = self._preferences.history_limit
        items = tuple(
            format_activity(item) for item in self.history.latest_activity(limit)
        )
        records = self.history.active_undo_records()
        if records:
            latest = records[0]
            expiry = (
                latest.expires_at.astimezone().strftime("%H:%M:%S")
                if latest.expires_at is not None
                else "no expiry"
            )
            undo = UndoAvailability(
                True,
                f"{latest.action_type.value}: {latest.item.display_name} "
                f"(expires {expiry})",
            )
        else:
            undo = UndoAvailability(False, "No undoable action is available.")
        return _ActivitySnapshot(items, undo)

    def _command_completed(self, outcome: _CommandOutcome) -> None:
        self._set_busy(False)
        self.view.add_message(
            ConversationMessage(
                "Omega",
                outcome.response,
                MessageKind.ASSISTANT,
                datetime.now(UTC),
            )
        )
        self.view.update_session_state(outcome.session_state)
        self.view.show_activity(outcome.activity.items)
        self.view.set_undo_availability(outcome.activity.undo)
        self._pending = outcome.confirmation
        if outcome.confirmation is not None:
            self.view.set_status(
                GuiStatus.AWAITING_CONFIRMATION, "Awaiting confirmation"
            )
            self.view.show_confirmation(outcome.confirmation)
            self._notify(
                "Confirmation required",
                outcome.confirmation.prompt,
                MessageKind.WARNING,
            )
        else:
            self.view.dismiss_confirmation()
        if outcome.activity_error:
            self._notify(
                "History unavailable",
                "Omega completed the request but could not refresh history.",
                MessageKind.WARNING,
            )

    def _activity_loaded(self, snapshot: _ActivitySnapshot) -> None:
        self._set_busy(False)
        self.view.show_activity(snapshot.items)
        self.view.set_undo_availability(snapshot.undo)
        self._notify(
            "History refreshed",
            f"Loaded {len(snapshot.items)} recent activity item(s).",
            MessageKind.SUCCESS,
        )

    def _preferences_loaded(self, preferences: GuiPreferences) -> None:
        self._preferences = preferences
        self.view.apply_preferences(preferences)

    def _preferences_saved(self, preferences: GuiPreferences) -> None:
        self._preferences = preferences
        self._set_busy(False)
        self.view.apply_preferences(preferences)
        self._notify(
            "Settings saved",
            "Your safe desktop preferences were updated.",
            MessageKind.SUCCESS,
        )
        self.refresh_activity()

    def _command_failed(self, error: BaseException) -> None:
        self._set_busy(False)
        self.logger.exception(
            "GUI background operation failed safely.",
            exc_info=(type(error), error, error.__traceback__),
        )
        self.view.add_message(
            ConversationMessage(
                "Omega",
                "Omega could not complete that desktop request safely.",
                MessageKind.ERROR,
                datetime.now(UTC),
            )
        )
        self.view.set_status(GuiStatus.ERROR, "Error")
        self._notify(
            "Request failed",
            "The request failed safely and was not retried.",
            MessageKind.ERROR,
        )

    def _task_error(self, error: BaseException) -> None:
        self.logger.exception(
            "GUI preference loading failed safely.",
            exc_info=(type(error), error, error.__traceback__),
        )
        self._notify(
            "Settings unavailable",
            "Safe default desktop settings are being used.",
            MessageKind.WARNING,
        )

    def _set_busy(self, busy: bool, detail: str = "Processing") -> None:
        self._busy = busy
        self.view.set_busy(busy)
        self.view.set_status(
            GuiStatus.PROCESSING if busy else GuiStatus.READY,
            detail if busy else "Ready",
        )

    def _notify(self, title: str, message: str, kind: MessageKind) -> None:
        if self._preferences.notifications_enabled:
            self.view.notify(Notification(title, message, kind))
