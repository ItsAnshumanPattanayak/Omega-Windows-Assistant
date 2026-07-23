"""Terminal adapter separated from Omega's session logic."""

from __future__ import annotations

from collections.abc import Callable
from typing import Protocol

from omega.scheduling import ScheduleNotification
from omega.session.session import OmegaSession


class NotificationSource(Protocol):
    def drain(self, limit: int = 20) -> tuple[ScheduleNotification, ...]: ...


class TerminalInterface:
    """Run a text session using injected input and output functions."""

    def __init__(
        self,
        session: OmegaSession,
        *,
        notifications: NotificationSource | None = None,
        input_func: Callable[[str], str] = input,
        output_func: Callable[[str], None] = print,
    ) -> None:
        self.session = session
        self._notifications = notifications
        self._input = input_func
        self._output = output_func

    def run(self) -> int:
        """Display startup instructions, process text, and exit cleanly."""
        self._output("Omega is ready.")
        self._output(f'Say "{self.session.activation_phrase}" to activate.')
        while not self.session.is_terminated:
            self._drain_notifications()
            timeout_message = self.session.check_timeout()
            if timeout_message:
                self._output(timeout_message)
            try:
                text = self._input("You: ")
            except (EOFError, KeyboardInterrupt):
                self._output(self.session.interrupt())
                break
            self._output(f"Omega: {self.session.handle_input(text)}")
            self._drain_notifications()
        return 0

    def _drain_notifications(self) -> None:
        if self._notifications is None:
            return
        for item in self._notifications.drain():
            self._output(
                f"Omega notification ({item.schedule_type.value}): "
                f"{item.title} — {item.message}"
            )
