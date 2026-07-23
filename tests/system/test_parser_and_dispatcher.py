from __future__ import annotations

from uuid import uuid4

import pytest

from omega.execution import SystemActionDispatcher
from omega.models import CommandSource, IntentType
from omega.safety import SafeExecutionGateway
from omega.system import PowerOperation
from omega.understanding.parser import CommandParser
from tests.system.test_manager import manager


@pytest.mark.parametrize(
    ("text", "intent"),
    [
        ("Show system information", IntentType.GET_SYSTEM_INFORMATION),
        ("What is my CPU usage?", IntentType.GET_CPU_USAGE),
        ("How much memory is available?", IntentType.GET_MEMORY_USAGE),
        ("Show disk space", IntentType.GET_DISK_USAGE),
        ("What is the battery percentage?", IntentType.GET_BATTERY_STATUS),
        ("Show network status", IntentType.GET_NETWORK_STATUS),
        ("List running processes", IntentType.LIST_PROCESSES),
        ("Show volume", IntentType.GET_VOLUME),
        ("Set volume to 40 percent", IntentType.SET_VOLUME),
        ("Increase brightness by 10 percent", IntentType.INCREASE_BRIGHTNESS),
        ("Open Bluetooth settings", IntentType.OPEN_WINDOWS_SETTINGS),
        ("Lock the computer", IntentType.LOCK_COMPUTER),
        ("Put the computer to sleep", IntentType.SLEEP_COMPUTER),
        ("Restart the computer", IntentType.RESTART_COMPUTER),
        ("Shut down the computer", IntentType.SHUT_DOWN_COMPUTER),
        ("Cancel the shutdown", IntentType.CANCEL_POWER_ACTION),
        ("Shut down Omega", IntentType.SHUTDOWN_ASSISTANT),
    ],
)
def test_system_parser_and_shutdown_distinction(text: str, intent: IntentType) -> None:
    result = CommandParser().parse(text, uuid4(), source=CommandSource.VOICE)
    assert result.command.intent is intent
    assert result.command.source is CommandSource.VOICE
    assert not result.requires_clarification


def test_invalid_percentage_requires_clarification() -> None:
    result = CommandParser().parse("Set volume to 101 percent")
    assert result.command.intent is IntentType.SET_VOLUME
    assert result.requires_clarification


def test_dispatcher_uses_gateway_and_exact_power_confirmation() -> None:
    system_manager, _, _, power = manager()
    gateway = SafeExecutionGateway()
    dispatcher = SystemActionDispatcher(system_manager, gateway)
    session_id = uuid4()
    parsed = CommandParser().parse("Restart the computer", session_id)
    pending = dispatcher.dispatch(parsed)
    assert pending is not None
    assert not pending.result.success
    assert "confirm restart computer" in pending.user_message
    assert power.requests == []

    assert gateway.handle_confirmation("yes", session_id) is not None
    assert power.requests == []

    parsed = CommandParser().parse("Restart the computer", session_id)
    dispatcher.dispatch(parsed)
    approved = gateway.handle_confirmation("confirm restart computer", session_id)
    assert approved is not None and approved.result.success
    assert len(power.requests) == 1
    assert power.requests[0].operation is PowerOperation.RESTART
