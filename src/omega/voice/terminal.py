"""Terminal presentation adapter for explicitly requested voice mode."""

from __future__ import annotations

from collections.abc import Callable
from threading import Event

from omega.core.exceptions import VoiceError
from omega.voice.models import VoiceEvent
from omega.voice.service import VoiceService


class VoiceTerminalInterface:
    """Display voice events while one explicit listener is running."""

    def __init__(
        self,
        service_factory: Callable[[Callable[[VoiceEvent], None]], VoiceService],
        *,
        output_func: Callable[[str], None] = print,
        wait_event: Event | None = None,
    ) -> None:
        self._service_factory = service_factory
        self._output = output_func
        self._wait_event = wait_event or Event()

    def run(self) -> int:
        """Start, monitor, and always close the optional voice service."""

        service: VoiceService | None = None
        try:
            service = self._service_factory(self._show_event)
            self._output("Omega voice mode is ready.")
            service.start()
            while service.running:
                self._wait_event.wait(0.1)
            return 0
        except KeyboardInterrupt:
            self._output("Omega voice mode was interrupted. Shutting down safely.")
            return 0
        except VoiceError as error:
            self._output(f"Omega voice mode is unavailable: {error}")
            return 1
        finally:
            if service is not None:
                service.stop()

    def _show_event(self, event: VoiceEvent) -> None:
        if event.transcript:
            self._output(f"You: {event.transcript}")
        if event.response:
            self._output(f"Omega: {event.response}")
        elif event.message and event.state.value in {
            "unavailable",
            "error",
            "idle",
        }:
            self._output(f"Omega: {event.message}")
