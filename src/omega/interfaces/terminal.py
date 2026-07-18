"""Terminal adapter separated from Omega's session logic."""

from __future__ import annotations

from collections.abc import Callable

from omega.session.session import OmegaSession


class TerminalInterface:
    """Run a text session using injected input and output functions."""

    def __init__(
        self,
        session: OmegaSession,
        *,
        input_func: Callable[[str], str] = input,
        output_func: Callable[[str], None] = print,
    ) -> None:
        self.session = session
        self._input = input_func
        self._output = output_func

    def run(self) -> int:
        """Display startup instructions, process text, and exit cleanly."""
        self._output("Omega is ready.")
        self._output(f'Say "{self.session.activation_phrase}" to activate.')
        while not self.session.is_terminated:
            timeout_message = self.session.check_timeout()
            if timeout_message:
                self._output(timeout_message)
            try:
                text = self._input("You: ")
            except (EOFError, KeyboardInterrupt):
                self._output(self.session.interrupt())
                break
            self._output(f"Omega: {self.session.handle_input(text)}")
        return 0
