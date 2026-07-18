"""Session manager for parsing and controlled application/file dispatch."""

from __future__ import annotations

import logging
from collections.abc import Callable, Mapping
from datetime import datetime
from time import monotonic
from typing import Any
from uuid import UUID, uuid4

from omega.core.exceptions import InvalidSessionTransitionError, ModelValidationError
from omega.execution.dispatcher import ApplicationActionDispatcher
from omega.execution.file_dispatcher import FileActionDispatcher
from omega.models import UserCommand
from omega.session.greeting import greeting_for
from omega.session.state import SessionState
from omega.understanding.parser import CommandParser
from omega.understanding.responses import format_parse_response

_ALLOWED_TRANSITIONS = {
    SessionState.INACTIVE: {SessionState.ACTIVE, SessionState.TERMINATED},
    SessionState.ACTIVE: {
        SessionState.INACTIVE,
        SessionState.SHUTTING_DOWN,
        SessionState.TERMINATED,
    },
    SessionState.SHUTTING_DOWN: {SessionState.TERMINATED},
    SessionState.TERMINATED: set(),
}


class OmegaSession:
    """Manage text lifecycle, history, parsing, and injected safe dispatch."""

    def __init__(
        self,
        user_settings: Mapping[str, Any],
        assistant_settings: Mapping[str, Any],
        *,
        monotonic_clock: Callable[[], float] = monotonic,
        now_provider: Callable[[], datetime] = datetime.now,
        logger: logging.Logger | None = None,
        parser: CommandParser | None = None,
        application_dispatcher: ApplicationActionDispatcher | None = None,
        file_dispatcher: FileActionDispatcher | None = None,
    ) -> None:
        self.display_name = self._required_text(user_settings, "display_name")
        self.activation_phrase = self._required_text(
            assistant_settings, "activation_phrase"
        )
        self.shutdown_phrase = self._required_text(
            assistant_settings, "shutdown_phrase"
        )
        self.timeout_seconds = self._timeout(assistant_settings)
        self._clock = monotonic_clock
        self._now_provider = now_provider
        self._logger = logger or logging.getLogger("omega.session")
        self._parser = parser or CommandParser()
        self._application_dispatcher = application_dispatcher
        self._file_dispatcher = file_dispatcher
        self.state = SessionState.INACTIVE
        self.session_id: UUID | None = None
        self.activated_at: float | None = None
        self.last_activity_at: float | None = None
        self._history: list[UserCommand] = []

    @staticmethod
    def _required_text(values: Mapping[str, Any], key: str) -> str:
        value = values.get(key)
        if not isinstance(value, str) or not value.strip():
            raise ModelValidationError(
                f"{key} must be a non-empty configuration value."
            )
        return value

    @staticmethod
    def _timeout(values: Mapping[str, Any]) -> float:
        value = values.get("active_session_timeout_seconds", 300)
        if isinstance(value, bool) or not isinstance(value, (int, float)) or value <= 0:
            raise ModelValidationError(
                "active_session_timeout_seconds must be positive."
            )
        return float(value)

    @property
    def history(self) -> tuple[UserCommand, ...]:
        """Return an immutable snapshot of current-process command history."""
        return tuple(self._history)

    @property
    def is_terminated(self) -> bool:
        """Report whether the terminal loop should exit."""
        return self.state is SessionState.TERMINATED

    @staticmethod
    def matches_phrase(text: str, phrase: str) -> bool:
        """Compare a standalone system phrase without command normalization."""
        return text.strip().casefold() == phrase.strip().casefold()

    def transition_to(self, target: SessionState) -> None:
        """Apply a legal state transition or raise a clear session exception."""
        if target not in _ALLOWED_TRANSITIONS[self.state]:
            raise InvalidSessionTransitionError(
                f"Cannot transition from {self.state.value} to {target.value}."
            )
        self.state = target

    def activate(self) -> str:
        """Activate Omega once and return a time-based personalized greeting."""
        if self.state is SessionState.TERMINATED:
            raise InvalidSessionTransitionError(
                "A terminated session cannot be activated."
            )
        if self.state is SessionState.ACTIVE:
            return f"Omega is already active, {self.display_name}. How can I help you?"
        self.transition_to(SessionState.ACTIVE)
        now = self._clock()
        self.session_id = uuid4()
        self.activated_at = now
        self.last_activity_at = now
        self._logger.info("Omega text session activated.")
        return greeting_for(self.display_name, self._now_provider())

    def shutdown(self) -> str:
        """Safely terminate this terminal session."""
        if self._application_dispatcher is not None:
            self._application_dispatcher.clear_pending_confirmations()
        if self._file_dispatcher is not None:
            self._file_dispatcher.clear_pending_confirmations()
        if self.state is SessionState.INACTIVE:
            self.transition_to(SessionState.TERMINATED)
            self._logger.info("Omega terminated while inactive.")
            return "Omega was not active. Shutting down now."
        if self.state is SessionState.ACTIVE:
            self.transition_to(SessionState.SHUTTING_DOWN)
            self.transition_to(SessionState.TERMINATED)
            self._logger.info("Omega text session shut down.")
            return f"Shutting down. Have a good day, {self.display_name}."
        if self.state is SessionState.SHUTTING_DOWN:
            self.transition_to(SessionState.TERMINATED)
            return f"Shutting down. Have a good day, {self.display_name}."
        return "Omega is already terminated."

    def interrupt(self) -> str:
        """Terminate gracefully in response to Ctrl+C or EOF."""
        if self._application_dispatcher is not None:
            self._application_dispatcher.clear_pending_confirmations()
        if self._file_dispatcher is not None:
            self._file_dispatcher.clear_pending_confirmations()
        if self.state is not SessionState.TERMINATED:
            if self.state is SessionState.ACTIVE:
                self.transition_to(SessionState.TERMINATED)
            elif self.state is SessionState.INACTIVE:
                self.transition_to(SessionState.TERMINATED)
            else:
                self.transition_to(SessionState.TERMINATED)
        self._logger.info("Omega terminal session interrupted.")
        return "Omega was interrupted. Shutting down safely."

    def check_timeout(self) -> str | None:
        """Deactivate a stale active session while preserving process history."""
        if self.state is not SessionState.ACTIVE or self.last_activity_at is None:
            return None
        if self._clock() - self.last_activity_at <= self.timeout_seconds:
            return None
        self.transition_to(SessionState.INACTIVE)
        if self._application_dispatcher is not None:
            self._application_dispatcher.clear_pending_confirmations()
        if self._file_dispatcher is not None:
            self._file_dispatcher.clear_pending_confirmations()
        self.session_id = None
        self.activated_at = None
        self.last_activity_at = None
        self._logger.info("Omega text session timed out.")
        return (
            "Omega became inactive because the session timed out. "
            'Say "Hello Omega" to activate me again.'
        )

    def handle_input(self, text: str) -> str:
        """Handle terminal text, creating command records only while active."""
        if self.state is SessionState.TERMINATED:
            return "Omega is terminated."
        if not isinstance(text, str) or not text.strip():
            return "Please enter a command."
        if self.matches_phrase(text, "help") or self.matches_phrase(text, "show help"):
            return (
                'Say "Hello Omega" to activate Omega. After activation, enter '
                'commands normally. Say "Shut down Omega" to exit.'
            )
        if self.matches_phrase(text, "status"):
            return f"Omega is {self.state.value}."
        if self.matches_phrase(text, self.shutdown_phrase):
            return self.shutdown()
        if self.state is SessionState.INACTIVE:
            if self.matches_phrase(text, self.activation_phrase):
                return self.activate()
            return 'Omega is inactive. Say "Hello Omega" to activate me.'
        if self.state is SessionState.ACTIVE:
            if self.matches_phrase(text, self.activation_phrase):
                return self.activate()
            if self.matches_phrase(text, "show history"):
                return (
                    "\n".join(command.original_text for command in self._history)
                    or "No commands received yet."
                )
            if self._application_dispatcher is not None:
                controlled = self._application_dispatcher.dispatch_control(
                    text, self.session_id
                )
                if controlled is not None:
                    self._history.append(controlled.command)
                    self.last_activity_at = self._clock()
                    return controlled.user_message
            if self._file_dispatcher is not None:
                controlled_file = self._file_dispatcher.dispatch_control(
                    text, self.session_id
                )
                if controlled_file is not None:
                    self._history.append(controlled_file.command)
                    self.last_activity_at = self._clock()
                    return controlled_file.user_message
            result = self._parser.parse(text, self.session_id)
            self._history.append(result.command)
            self.last_activity_at = self._clock()
            if self._application_dispatcher is not None:
                dispatched = self._application_dispatcher.dispatch(result)
                if dispatched is not None:
                    return dispatched.user_message
            if self._file_dispatcher is not None:
                dispatched_file = self._file_dispatcher.dispatch(result)
                if dispatched_file is not None:
                    return dispatched_file.user_message
            return format_parse_response(result)
        raise InvalidSessionTransitionError(
            "Session cannot accept input while shutting down."
        )
