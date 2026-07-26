from datetime import datetime

from omega.calendar import CalendarService
from omega.execution import CalendarActionDispatcher
from omega.safety import SafeExecutionGateway
from omega.session.session import OmegaSession


def test_calendar_uses_normal_session_lifecycle(
    service: CalendarService, now: datetime
) -> None:
    clock = [1.0]
    dispatcher = CalendarActionDispatcher(service, SafeExecutionGateway(), lambda: now)
    session = OmegaSession(
        {"display_name": "Anshuman"},
        {
            "activation_phrase": "Hello Omega",
            "shutdown_phrase": "Shut down Omega",
            "active_session_timeout_seconds": 5,
        },
        monotonic_clock=lambda: clock[0],
        calendar_dispatcher=dispatcher,
    )
    session.handle_input("Hello Omega")
    assert "Planning" in session.handle_input("show my calendar for today")
    clock[0] = 7
    timeout = session.check_timeout()
    assert timeout is not None and "timed out" in timeout.casefold()


def test_shutdown_clears_calendar_session(
    service: CalendarService, now: datetime
) -> None:
    dispatcher = CalendarActionDispatcher(service, SafeExecutionGateway(), lambda: now)
    session = OmegaSession(
        {"display_name": "Anshuman"},
        {
            "activation_phrase": "Hello Omega",
            "shutdown_phrase": "Shut down Omega",
            "active_session_timeout_seconds": 5,
        },
        calendar_dispatcher=dispatcher,
    )
    session.handle_input("Hello Omega")
    session.handle_input("show my calendar for today")
    session.handle_input("Shut down Omega")
    assert session.session_id not in service._selections
