"""Narrow dispatcher for allowlisted application intents only."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID

from omega.applications.manager import ApplicationManager
from omega.applications.registry import ApplicationRegistry
from omega.models import (
    Action,
    ActionResult,
    ActionStatus,
    CommandEntity,
    ConfirmationStatus,
    EntityType,
    IntentType,
    PermissionDecision,
    RiskLevel,
    UserCommand,
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
    CONFIRM_FORCE_CLOSE = "confirm force close"
    CANCEL_FORCE_CLOSE = "cancel force close"
    FORCE_CLOSE = "force close"
    CONFIRM_CLOSE = "confirm close"
    CANCEL_CLOSE = "cancel close"


@dataclass(frozen=True)
class ApplicationDispatchResult:
    """The command, action proposal, and structured application result."""

    command: UserCommand
    action: Action
    result: ActionResult

    @property
    def user_message(self) -> str:
        return self.result.user_message


class ApplicationActionDispatcher:
    """Dispatch only complete application commands with canonical entity values."""

    def __init__(
        self, manager: ApplicationManager, registry: ApplicationRegistry
    ) -> None:
        self.manager = manager
        self.registry = registry

    def dispatch(self, parsed: CommandParseResult) -> ApplicationDispatchResult | None:
        """Return None without side effects for unsupported or incomplete commands."""
        command = parsed.command
        if (
            not parsed.matched
            or parsed.requires_clarification
            or command.intent not in _APPLICATION_INTENTS
        ):
            return None
        application_id = self._application_id(command)
        if application_id is None or self.registry.get(application_id) is None:
            return None
        definition = self.registry.get(application_id)
        if definition is None:
            return None

        needs_confirmation = (
            command.intent is IntentType.CLOSE_APPLICATION
            and definition.supports_graceful_close
            and definition.requires_close_confirmation
        )
        risk = (
            RiskLevel.MEDIUM
            if command.intent is IntentType.CLOSE_APPLICATION
            else RiskLevel.LOW
        )
        action = self._action(command, application_id, risk, needs_confirmation)
        if command.intent is IntentType.OPEN_APPLICATION:
            result = self.manager.open_application(
                application_id, action.action_id, command.command_id
            )
        elif command.intent is IntentType.CHECK_APPLICATION_STATUS:
            result = self.manager.check_application_status(
                application_id, action.action_id, command.command_id
            )
        else:
            result = self.manager.request_close_application(
                application_id, action.action_id, command.command_id
            )
        return ApplicationDispatchResult(command, action, result)

    def dispatch_control(
        self, text: str, session_id: UUID | None = None
    ) -> ApplicationDispatchResult | None:
        """Handle exact, tightly scoped close-control phrases."""
        normalized = " ".join(text.strip().split()).casefold()
        matched: tuple[ApplicationControlCommand, str] | None = None
        for command_type in ApplicationControlCommand:
            prefix = command_type.value + " "
            if normalized.startswith(prefix):
                target = normalized[len(prefix) :]
                if target:
                    matched = command_type, target
                break
        if matched is None:
            return None
        command_type, target = matched
        definition = self.registry.resolve(target)
        if definition is None:
            return None

        raw_match = re.search(re.escape(target), text, re.IGNORECASE)
        raw_value = raw_match.group(0) if raw_match else target
        command = UserCommand(
            text,
            normalized_text=normalized,
            intent=IntentType.CLOSE_APPLICATION,
            entities=[
                CommandEntity(
                    EntityType.APPLICATION,
                    definition.application_id,
                    raw_value=raw_value,
                    name="application_name",
                )
            ],
            confidence=1.0,
            session_id=session_id,
        )
        force = command_type in {
            ApplicationControlCommand.FORCE_CLOSE,
            ApplicationControlCommand.CONFIRM_FORCE_CLOSE,
            ApplicationControlCommand.CANCEL_FORCE_CLOSE,
        }
        requires_confirmation = command_type is ApplicationControlCommand.FORCE_CLOSE
        action = self._action(
            command,
            definition.application_id,
            RiskLevel.HIGH if force else RiskLevel.MEDIUM,
            requires_confirmation,
        )
        method = {
            ApplicationControlCommand.CONFIRM_CLOSE: (
                self.manager.confirm_close_application
            ),
            ApplicationControlCommand.CANCEL_CLOSE: (
                self.manager.cancel_close_application
            ),
            ApplicationControlCommand.FORCE_CLOSE: (
                self.manager.request_force_close_application
            ),
            ApplicationControlCommand.CONFIRM_FORCE_CLOSE: (
                self.manager.confirm_force_close_application
            ),
            ApplicationControlCommand.CANCEL_FORCE_CLOSE: (
                self.manager.cancel_force_close_application
            ),
        }[command_type]
        result = method(definition.application_id, action.action_id, command.command_id)
        return ApplicationDispatchResult(command, action, result)

    def clear_pending_confirmations(self) -> None:
        """Drop session-scoped close confirmations."""
        self.manager.clear_pending_confirmations()

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
    def _action(
        command: UserCommand,
        application_id: str,
        risk: RiskLevel,
        requires_confirmation: bool,
    ) -> Action:
        return Action(
            command_id=command.command_id,
            intent=command.intent,
            parameters={"application_id": application_id},
            risk_level=risk,
            status=(
                ActionStatus.AWAITING_CONFIRMATION
                if requires_confirmation
                else ActionStatus.PENDING
            ),
            permission_decision=(
                PermissionDecision.REQUIRE_CONFIRMATION
                if requires_confirmation
                else PermissionDecision.ALLOW
            ),
            confirmation_status=(
                ConfirmationStatus.PENDING
                if requires_confirmation
                else ConfirmationStatus.NOT_REQUIRED
            ),
            requires_confirmation=requires_confirmation,
        )
