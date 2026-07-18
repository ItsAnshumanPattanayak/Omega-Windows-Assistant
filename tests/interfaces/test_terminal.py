from omega.interfaces import TerminalInterface
from omega.session import OmegaSession


def test_terminal_lifecycle_and_eof() -> None:
    messages: list[str] = []
    inputs = iter(["Hello Omega", "Open Chrome", "Shut down Omega"])
    session = OmegaSession(
        {"display_name": "Anshuman"},
        {
            "activation_phrase": "Hello Omega",
            "shutdown_phrase": "Shut down Omega",
            "active_session_timeout_seconds": 300,
        },
    )
    terminal = TerminalInterface(
        session, input_func=lambda _: next(inputs), output_func=messages.append
    )
    assert terminal.run() == 0
    assert messages[0] == "Omega is ready."
    assert any("received your command" in message for message in messages)


def test_terminal_handles_eof() -> None:
    messages: list[str] = []
    session = OmegaSession(
        {"display_name": "Anshuman"},
        {
            "activation_phrase": "Hello Omega",
            "shutdown_phrase": "Shut down Omega",
            "active_session_timeout_seconds": 300,
        },
    )
    terminal = TerminalInterface(
        session,
        input_func=lambda _: (_ for _ in ()).throw(EOFError()),
        output_func=messages.append,
    )
    assert terminal.run() == 0
    assert messages[-1] == "Omega was interrupted. Shutting down safely."
