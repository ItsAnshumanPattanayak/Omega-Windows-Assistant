"""Application action adapter protected by the central execution gateway."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID

from omega.applications.manager import ApplicationManager
from omega.applications.registry import ApplicationRegistry
from omega.models import (
    Action,
    ActionResult,
    ConfirmationStatus,
    EntityType,
    IntentType,
    PermissionDecision,
    RiskLevel,
    UserCommand,
)
from omega.safety import (
    ConfirmationSpec,
    GatewayDispatchResult,
    ResourceFingerprint,
    SafeExecutionGateway,
    SafetyContext,
)
from omega.understanding.result import CommandParseResult

_APPLICATION_INTENTS = frozenset(
    {
        IntentType.OPEN_APPLICATION,
        IntentType.CLOSE_APPLICATION,
        IntentType.CHECK_APPLICATION_STATUS,
    }
)


class ApplicationControlCommand(StrEnum):
    """Legacy public names retained; central confirmation owns their behavior."""

    CONFIRM_FORCE_CLOSE = "confirm force close"
    CANCEL_FORCE_CLOSE = "cancel force close"
    FORCE_CLOSE = "force close"
    CONFIRM_CLOSE = "confirm close"
    CANCEL_CLOSE = "cancel close"


@dataclass(frozen=True)
class ApplicationDispatchResult:
    command: UserCommand
    action: Action
    result: ActionResult

    @property
    def user_message(self) -> str:
        return self.result.user_message

    @classmethod
    def from_gateway(cls, value: GatewayDispatchResult) -> ApplicationDispatchResult:
        return cls(value.command, value.action, value.result)


class ApplicationActionDispatcher:
    """Build typed application proposals and submit every one to the gateway."""

    def __init__(
        self,
        manager: ApplicationManager,
        registry: ApplicationRegistry,
        *,
        gateway: SafeExecutionGateway | None = None,
    ) -> None:
        self.manager = manager
        self.registry = registry
        self.gateway = gateway or SafeExecutionGateway()

    def dispatch(self, parsed: CommandParseResult) -> ApplicationDispatchResult | None:
        command = parsed.command
        if (
            not parsed.matched
            or parsed.requires_clarification
            or command.intent not in _APPLICATION_INTENTS
        ):
            return None
        application_id = self._application_id(command)
        definition = self.registry.get(application_id) if application_id else None
        if application_id is None or definition is None:
            return None
        action = self._action(command, application_id)
        session_id = command.session_id or UUID(int=0)
        context = SafetyContext(
            command=command,
            action=action,
            session_id=session_id,
            application_id=application_id,
            logical_source=definition.display_name,
            target_type="application",
        )
        confirmation = None
        fingerprint = None

        def revalidator() -> ResourceFingerprint | None:
            return None

        if command.intent is IntentType.OPEN_APPLICATION:

            def executor() -> ActionResult:
                return self.manager.open_application(
                    application_id, action.action_id, command.command_id
                )

        elif command.intent is IntentType.CHECK_APPLICATION_STATUS:

            def executor() -> ActionResult:
                return self.manager.check_application_status(
                    application_id, action.action_id, command.command_id
                )

        else:
            alias = definition.aliases[0].title()
            exact = f"confirm close {alias}"
            confirmation = ConfirmationSpec(
                definition.display_name,
                f"Closing {definition.display_name} may discard unsaved work. "
                f'Type "{exact}" to continue.',
                exact,
                f"cancel close {alias}",
            )
            fingerprint = self._fingerprint(application_id)

            def revalidator() -> ResourceFingerprint | None:
                return self._fingerprint(application_id)

            def executor() -> ActionResult:
                return self.manager.close_application(
                    application_id, action.action_id, command.command_id
                )

        value = self.gateway.submit(
            context,
            executor,
            confirmation=confirmation,
            fingerprint=fingerprint,
            revalidator=revalidator,
        )
        return ApplicationDispatchResult.from_gateway(value)

    def dispatch_control(
        self, text: str, session_id: UUID | None = None
    ) -> ApplicationDispatchResult | None:
        handled = self.gateway.handle_confirmation(text, session_id or UUID(int=0))
        return ApplicationDispatchResult.from_gateway(handled) if handled else None

    def clear_pending_confirmations(self) -> None:
        self.gateway.clear_confirmations()
        clear = getattr(self.manager, "clear_pending_confirmations", None)
        if callable(clear):
            clear()

    def _fingerprint(self, application_id: str) -> ResourceFingerprint:
        definition = self.registry.get(application_id)
        if definition is None:
            return ResourceFingerprint("application", application_id, False)
        inspect = getattr(self.manager, "inspect_application_fingerprint", None)
        if callable(inspect):
            result = inspect(application_id)
            if isinstance(result, ResourceFingerprint):
                return result
        return ResourceFingerprint("application", application_id, True)

    @staticmethod
    def _application_id(command: UserCommand) -> str | None:
        entities = [
            entity
            for entity in command.entities
            if entity.entity_type is EntityType.APPLICATION
            and entity.name == "application_name"
        ]
        if len(entities) != 1 or not isinstance(entities[0].value, str):
            return None
        return entities[0].value

    @staticmethod
    def _action(command: UserCommand, application_id: str) -> Action:
        provisional = {
            IntentType.OPEN_APPLICATION: RiskLevel.LOW,
            IntentType.CHECK_APPLICATION_STATUS: RiskLevel.LOW,
            IntentType.CLOSE_APPLICATION: RiskLevel.HIGH,
        }[command.intent]
        return Action(
            command_id=command.command_id,
            intent=command.intent,
            parameters={"application_id": application_id},
            risk_level=provisional,
            permission_decision=PermissionDecision.ALLOW,
            confirmation_status=ConfirmationStatus.NOT_REQUIRED,
            requires_confirmation=False,
        )
