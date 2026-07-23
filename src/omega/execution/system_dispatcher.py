"""System-action proposals routed exclusively through the safety gateway."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from omega.models import (
    Action,
    ActionResult,
    ConfirmationStatus,
    IntentType,
    PermissionDecision,
    RiskLevel,
    UserCommand,
)
from omega.models._serialization import JsonValue
from omega.safety import (
    ConfirmationSpec,
    GatewayDispatchResult,
    SafeExecutionGateway,
    SafetyContext,
)
from omega.system import PowerOperation, SystemManager
from omega.understanding.result import CommandParseResult

_INFORMATION = {
    IntentType.GET_SYSTEM_INFORMATION: "system",
    IntentType.GET_CPU_USAGE: "cpu",
    IntentType.GET_MEMORY_USAGE: "memory",
    IntentType.GET_DISK_USAGE: "disk",
    IntentType.GET_BATTERY_STATUS: "battery",
    IntentType.GET_NETWORK_STATUS: "network",
    IntentType.LIST_PROCESSES: "process",
    IntentType.SEARCH_PROCESS: "process",
    IntentType.GET_PROCESS_INFORMATION: "process",
}
_AUDIO = {
    IntentType.GET_VOLUME: "get",
    IntentType.SET_VOLUME: "set",
    IntentType.INCREASE_VOLUME: "increase",
    IntentType.DECREASE_VOLUME: "decrease",
    IntentType.MUTE_VOLUME: "mute",
    IntentType.UNMUTE_VOLUME: "unmute",
}
_BRIGHTNESS = {
    IntentType.GET_BRIGHTNESS: "get",
    IntentType.SET_BRIGHTNESS: "set",
    IntentType.INCREASE_BRIGHTNESS: "increase",
    IntentType.DECREASE_BRIGHTNESS: "decrease",
}
_POWER = {
    IntentType.LOCK_COMPUTER: PowerOperation.LOCK,
    IntentType.SLEEP_COMPUTER: PowerOperation.SLEEP,
    IntentType.HIBERNATE_COMPUTER: PowerOperation.HIBERNATE,
    IntentType.SIGN_OUT_USER: PowerOperation.SIGN_OUT,
    IntentType.RESTART_COMPUTER: PowerOperation.RESTART,
    IntentType.SHUT_DOWN_COMPUTER: PowerOperation.SHUTDOWN,
    IntentType.CANCEL_POWER_ACTION: PowerOperation.CANCEL,
}
_SYSTEM_INTENTS = frozenset(
    {*_INFORMATION, *_AUDIO, *_BRIGHTNESS, IntentType.OPEN_WINDOWS_SETTINGS, *_POWER}
)


@dataclass(frozen=True)
class SystemDispatchResult:
    command: UserCommand
    action: Action
    result: ActionResult

    @property
    def user_message(self) -> str:
        return self.result.user_message

    @classmethod
    def from_gateway(cls, value: GatewayDispatchResult) -> SystemDispatchResult:
        return cls(value.command, value.action, value.result)


class SystemActionDispatcher:
    """Translate trusted parsed values into one gateway-submitted operation."""

    def __init__(self, manager: SystemManager, gateway: SafeExecutionGateway) -> None:
        self.manager = manager
        self.gateway = gateway

    def dispatch(self, parsed: CommandParseResult) -> SystemDispatchResult | None:
        command = parsed.command
        if (
            not parsed.matched
            or parsed.requires_clarification
            or command.intent not in _SYSTEM_INTENTS
        ):
            return None
        risk = self._risk(command.intent)
        action = Action(
            command_id=command.command_id,
            intent=command.intent,
            parameters=self._parameters(command),
            risk_level=risk,
            permission_decision=PermissionDecision.ALLOW,
            confirmation_status=ConfirmationStatus.NOT_REQUIRED,
            requires_confirmation=False,
        )
        operation = _POWER.get(command.intent)
        context = SafetyContext(
            command=command,
            action=action,
            session_id=command.session_id or UUID(int=0),
            logical_source=operation.value if operation else command.intent.value,
            target_type="windows_system",
            additional_context={"system_action": True},
        )
        confirmation = self._confirmation(operation)
        result = self.gateway.submit(
            context,
            lambda: self._execute(command, action),
            confirmation=confirmation,
        )
        return SystemDispatchResult.from_gateway(result)

    def _execute(self, command: UserCommand, action: Action) -> ActionResult:
        intent = command.intent
        if intent in _INFORMATION:
            return self.manager.information_result(
                action.action_id,
                command.command_id,
                _INFORMATION[intent],
                self._text(command, "process_name"),
            )
        if intent in _AUDIO:
            return self.manager.audio_result(
                action.action_id,
                command.command_id,
                _AUDIO[intent],
                self._number(command),
            )
        if intent in _BRIGHTNESS:
            return self.manager.brightness_result(
                action.action_id,
                command.command_id,
                _BRIGHTNESS[intent],
                self._number(command),
            )
        if intent is IntentType.OPEN_WINDOWS_SETTINGS:
            page = self._text(command, "settings_page")
            if page is None:
                raise ValueError("Missing allowlisted Settings page.")
            return self.manager.open_settings(
                action.action_id, command.command_id, page
            )
        operation = _POWER[intent]
        return self.manager.power_result(
            action.action_id, command.command_id, operation
        )

    @staticmethod
    def _risk(intent: IntentType) -> RiskLevel:
        if intent in _INFORMATION or intent in {
            IntentType.GET_VOLUME,
            IntentType.GET_BRIGHTNESS,
            IntentType.OPEN_WINDOWS_SETTINGS,
            IntentType.CANCEL_POWER_ACTION,
        }:
            return RiskLevel.LOW
        if intent in _AUDIO or intent in _BRIGHTNESS:
            return RiskLevel.MEDIUM
        if intent in {
            IntentType.LOCK_COMPUTER,
            IntentType.SLEEP_COMPUTER,
            IntentType.HIBERNATE_COMPUTER,
        }:
            return RiskLevel.HIGH
        return RiskLevel.CRITICAL

    @staticmethod
    def _confirmation(operation: PowerOperation | None) -> ConfirmationSpec | None:
        if operation is None or operation is PowerOperation.CANCEL:
            return None
        phrases = {
            PowerOperation.LOCK: "lock computer",
            PowerOperation.SLEEP: "sleep computer",
            PowerOperation.HIBERNATE: "hibernate computer",
            PowerOperation.SIGN_OUT: "sign out",
            PowerOperation.RESTART: "restart computer",
            PowerOperation.SHUTDOWN: "shut down computer",
        }
        target = phrases[operation]
        return ConfirmationSpec(
            target,
            f'This affects the Windows session. Type "confirm {target}" to continue.',
            f"confirm {target}",
            f"cancel {target}",
        )

    @staticmethod
    def _text(command: UserCommand, name: str) -> str | None:
        values = [
            item.value
            for item in command.entities
            if item.name == name and isinstance(item.value, str)
        ]
        return values[0] if len(values) == 1 else None

    @staticmethod
    def _number(command: UserCommand) -> int | None:
        values = [
            item.value
            for item in command.entities
            if item.name == "percentage"
            and isinstance(item.value, int)
            and not isinstance(item.value, bool)
        ]
        return values[0] if len(values) == 1 else None

    @classmethod
    def _parameters(cls, command: UserCommand) -> dict[str, JsonValue]:
        parameters: dict[str, JsonValue] = {}
        percentage = cls._number(command)
        if percentage is not None:
            parameters["percentage"] = percentage
        for name in ("settings_page", "process_name"):
            value = cls._text(command, name)
            if value is not None:
                parameters[name] = value
        operation = _POWER.get(command.intent)
        if operation is not None:
            parameters["power_operation"] = operation.value
        return parameters
