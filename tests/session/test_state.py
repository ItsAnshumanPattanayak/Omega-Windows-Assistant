import pytest

from omega.core.exceptions import InvalidSessionTransitionError
from omega.session import OmegaSession, SessionState


def test_state_and_transitions() -> None:
    session = OmegaSession(
        {"display_name": "Anshuman"},
        {
            "activation_phrase": "Hello Omega",
            "shutdown_phrase": "Shut down Omega",
            "active_session_timeout_seconds": 300,
        },
    )
    assert session.state is SessionState.INACTIVE
    session.transition_to(SessionState.ACTIVE)
    session.transition_to(SessionState.INACTIVE)
    session.transition_to(SessionState.TERMINATED)
    with pytest.raises(InvalidSessionTransitionError):
        session.transition_to(SessionState.ACTIVE)
