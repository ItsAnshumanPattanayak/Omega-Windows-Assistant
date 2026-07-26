from datetime import datetime
from types import MethodType
from uuid import UUID, uuid4

import pytest

from omega.calendar import CalendarService, FakeCalendarProvider
from omega.execution import CalendarActionDispatcher
from omega.gui.controller import GuiController
from omega.models import IntentType
from omega.safety import SafeExecutionGateway
from omega.understanding.parser import CommandParser


@pytest.mark.parametrize(
    ("text", "intent"),
    [
        ("calendar status", IntentType.CALENDAR_STATUS),
        ("show my calendar for today", IntentType.LIST_CALENDAR_EVENTS),
        ("show my events today", IntentType.LIST_CALENDAR_EVENTS),
        ("what is on my calendar tomorrow", IntentType.LIST_CALENDAR_EVENTS),
        ("show my calendar this week", IntentType.LIST_CALENDAR_EVENTS),
        ("search my calendar for planning", IntentType.SEARCH_CALENDAR_EVENTS),
        ("find my meeting with Anshuman", IntentType.SEARCH_CALENDAR_EVENTS),
        ("open event number 1", IntentType.READ_CALENDAR_EVENT),
        ("show my availability for tomorrow", IntentType.SHOW_CALENDAR_AVAILABILITY),
        ("am I free tomorrow at 3 PM", IntentType.SHOW_CALENDAR_AVAILABILITY),
        ("show my agenda for this week", IntentType.SHOW_CALENDAR_AGENDA),
        (
            "schedule event Planning tomorrow at 4 pm for 30 minutes",
            IntentType.CREATE_CALENDAR_EVENT,
        ),
        ("delete this event", IntentType.DELETE_CALENDAR_EVENT),
        ("accept this invitation", IntentType.RESPOND_CALENDAR_INVITATION),
    ],
)
def test_calendar_parser_intents(text: str, intent: IntentType) -> None:
    result = CommandParser().parse(text)
    assert (
        result.command.intent is intent
        and result.matched
        and not result.requires_clarification
    )


def test_create_parser_requires_unambiguous_complete_time() -> None:
    result = CommandParser().parse("schedule event Planning tomorrow at 4")
    assert result.requires_clarification
    result = CommandParser().parse("schedule a meeting tomorrow at 4 pm")
    assert (
        result.requires_clarification and "duration_minutes" in result.missing_entities
    )
    result = CommandParser().parse(
        "schedule event Planning tomorrow at 4 pm for 30 minutes"
    )
    assert {item.name for item in result.command.entities} >= {
        "event_title",
        "event_day",
        "event_time",
        "duration_minutes",
    }


def _dispatch(dispatcher: CalendarActionDispatcher, text: str, session: UUID):
    value = dispatcher.dispatch(CommandParser().parse(text, session))
    assert value is not None
    return value


def test_reads_and_confirmed_create_use_gateway(
    service: CalendarService, provider: FakeCalendarProvider, now: datetime
) -> None:
    session = uuid4()
    gateway = SafeExecutionGateway()
    dispatcher = CalendarActionDispatcher(service, gateway, lambda: now)
    listed = _dispatch(dispatcher, "show my calendar for today", session)
    assert listed.result.success and "Planning" in listed.user_message
    proposal = _dispatch(
        dispatcher, "schedule event Review tomorrow at 4 pm for 30 minutes", session
    )
    assert not proposal.result.success and provider.create_count == 0
    pending = gateway.confirmations.get(session)
    assert pending is not None
    confirmed = gateway.handle_confirmation(pending.expected_confirmation, session)
    assert (
        confirmed is not None
        and confirmed.result.success
        and provider.create_count == 1
    )
    replay = gateway.handle_confirmation(pending.expected_confirmation, session)
    assert (
        replay is not None and not replay.result.success and provider.create_count == 1
    )


def test_delete_requires_exact_confirmation(
    service: CalendarService, provider: FakeCalendarProvider, now: datetime
) -> None:
    session = uuid4()
    gateway = SafeExecutionGateway()
    dispatcher = CalendarActionDispatcher(service, gateway, lambda: now)
    _dispatch(dispatcher, "show my calendar for today", session)
    _dispatch(dispatcher, "open event number 1", session)
    proposal = _dispatch(dispatcher, "delete this event", session)
    assert not proposal.result.success and provider.delete_count == 0
    pending = gateway.confirmations.get(session)
    assert pending is not None
    wrong = gateway.handle_confirmation("yes", session)
    assert wrong is not None and not wrong.result.success and provider.delete_count == 0


def test_disabled_provider_fails_safely(configuration, now) -> None:
    disabled = type(configuration)()
    dispatcher = CalendarActionDispatcher(
        CalendarService(disabled), SafeExecutionGateway(), lambda: now
    )
    result = _dispatch(dispatcher, "show my calendar for today", uuid4())
    assert not result.result.success and "disabled" in result.user_message


def test_gui_calendar_helpers_use_normal_command_lifecycle() -> None:
    controller = object.__new__(GuiController)
    submitted: list[str] = []
    controller.submit_command = MethodType(
        lambda self, text: submitted.append(text) or True, controller
    )
    assert controller.list_calendar_events("today")
    assert controller.search_calendar("planning")
    assert controller.create_calendar_event("Review", "tomorrow", "4 pm", 30)
    assert submitted == [
        "show my calendar for today",
        "search my calendar for planning",
        "schedule event Review tomorrow at 4 pm for 30 minutes",
    ]


def test_command_history_redaction(service, now) -> None:
    dispatcher = CalendarActionDispatcher(service, SafeExecutionGateway(), lambda: now)
    result = _dispatch(
        dispatcher, "search my calendar for confidential merger", uuid4()
    )
    assert result.command.original_text == "[calendar command: search_calendar_events]"
    assert "confidential" not in result.command.original_text


def test_no_dynamic_execution_or_network_primitives() -> None:
    import omega.calendar.fake as fake

    source = open(fake.__file__, encoding="utf-8").read()
    assert (
        "eval(" not in source
        and "exec(" not in source
        and "subprocess" not in source
        and "pickle" not in source
    )
