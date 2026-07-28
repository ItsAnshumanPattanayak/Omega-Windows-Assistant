"""Cooperative cancellation with no process or thread termination."""

from threading import Event

from omega.ai.exceptions import AiRequestCancelledError


class AiCancellationToken:
    """Thread-safe cooperative cancellation token passed to providers."""

    def __init__(self) -> None:
        self._event = Event()

    @property
    def cancelled(self) -> bool:
        return self._event.is_set()

    def cancel(self) -> None:
        self._event.set()

    def raise_if_cancelled(self) -> None:
        if self.cancelled:
            raise AiRequestCancelledError("Local AI generation was cancelled.")
