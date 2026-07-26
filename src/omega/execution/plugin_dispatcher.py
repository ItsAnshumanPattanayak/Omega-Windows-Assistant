"""Plugin management routed through Omega's central safety gateway."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from uuid import UUID

from omega.models import (
    Action,
    ActionResult,
    ConfirmationStatus,
    ErrorCategory,
    IntentType,
    OmegaErrorDetails,
    PermissionDecision,
    RiskLevel,
    UserCommand,
)
from omega.plugins import PluginManager, PluginPermission
from omega.plugins.exceptions import PluginError
from omega.safety import (
    ConfirmationSpec,
    ResourceFingerprint,
    SafeExecutionGateway,
    SafetyContext,
)
from omega.understanding.result import CommandParseResult

_INTENTS = frozenset(
    {
        IntentType.LIST_PLUGINS,
        IntentType.SHOW_PLUGIN,
        IntentType.VALIDATE_PLUGIN_PACKAGE,
        IntentType.INSTALL_PLUGIN,
        IntentType.ENABLE_PLUGIN,
        IntentType.DISABLE_PLUGIN,
        IntentType.REMOVE_PLUGIN,
        IntentType.SHOW_PLUGIN_PERMISSIONS,
        IntentType.GRANT_PLUGIN_PERMISSION,
        IntentType.REVOKE_PLUGIN_PERMISSION,
        IntentType.RELOAD_PLUGIN,
        IntentType.SHOW_FAILED_PLUGINS,
    }
)
_CONFIRMED = {
    IntentType.INSTALL_PLUGIN,
    IntentType.ENABLE_PLUGIN,
    IntentType.GRANT_PLUGIN_PERMISSION,
    IntentType.REMOVE_PLUGIN,
}
_READ_ONLY = {
    IntentType.LIST_PLUGINS,
    IntentType.SHOW_PLUGIN,
    IntentType.VALIDATE_PLUGIN_PACKAGE,
    IntentType.SHOW_PLUGIN_PERMISSIONS,
    IntentType.SHOW_FAILED_PLUGINS,
}


@dataclass(frozen=True)
class PluginDispatchResult:
    command: UserCommand
    action: Action
    result: ActionResult

    @property
    def user_message(self) -> str:
        return self.result.user_message


class PluginDispatcher:
    def __init__(self, manager: PluginManager, gateway: SafeExecutionGateway) -> None:
        self.manager, self.gateway = manager, gateway

    def dispatch(self, parsed: CommandParseResult) -> PluginDispatchResult | None:
        command = parsed.command
        if (
            not parsed.matched
            or parsed.requires_clarification
            or command.intent not in _INTENTS
        ):
            return None
        action = Action(
            command.command_id,
            command.intent,
            parameters={"plugin_operation": command.intent.value},
            risk_level=(
                RiskLevel.HIGH
                if command.intent is IntentType.REMOVE_PLUGIN
                else RiskLevel.LOW if command.intent in _READ_ONLY else RiskLevel.MEDIUM
            ),
            permission_decision=PermissionDecision.ALLOW,
            confirmation_status=ConfirmationStatus.NOT_REQUIRED,
            requires_confirmation=False,
        )
        safe_command = self._redacted(command)
        context = SafetyContext(
            safe_command,
            action,
            command.session_id or UUID(int=0),
            logical_source=command.intent.value,
            target_type="plugin",
            additional_context={"shell_like": False, "plugin_scope_only": True},
        )

        def execute() -> ActionResult:
            try:
                message = self._execute(command)
                return ActionResult.success_result(action.action_id, message, message)
            except (PluginError, OSError, LookupError) as error:
                return self._failure(safe_command, action, str(error))

        if command.intent not in _CONFIRMED:
            submitted = self.gateway.submit(context, execute)
        else:
            spec, fingerprint, revalidator = self._confirmation(command)
            submitted = self.gateway.submit(
                context,
                execute,
                confirmation=spec,
                fingerprint=fingerprint,
                revalidator=revalidator,
            )
        return PluginDispatchResult(
            submitted.command, submitted.action, submitted.result
        )

    def clear_session(self) -> None:
        self.manager.clear_session()

    def _confirmation(self, command: UserCommand) -> tuple[
        ConfirmationSpec,
        ResourceFingerprint,
        Callable[[], ResourceFingerprint | None],
    ]:
        if command.intent is IntentType.INSTALL_PLUGIN:
            path = Path(self._required(command, "plugin_package_path"))
            manifest = self.manager.installer.validate(path)
            payload = path.read_bytes()
            fingerprint = ResourceFingerprint(
                "plugin_package",
                str(path.name),
                True,
                size=len(payload),
                digest=sha256(payload).hexdigest(),
            )
            target = manifest.plugin_id

            def revalidator() -> ResourceFingerprint | None:
                current = path.read_bytes()
                return ResourceFingerprint(
                    "plugin_package",
                    str(path.name),
                    True,
                    size=len(current),
                    digest=sha256(current).hexdigest(),
                )

        else:
            item = self.manager.select(self._required(command, "plugin_reference"))
            fingerprint = ResourceFingerprint(
                "plugin", item.manifest.plugin_id, True, digest=item.fingerprint
            )
            target = item.manifest.plugin_id

            def revalidator() -> ResourceFingerprint | None:
                current = self.manager.select(item.manifest.plugin_id)
                return ResourceFingerprint(
                    "plugin",
                    current.manifest.plugin_id,
                    True,
                    digest=current.fingerprint,
                )

        phrase = f"confirm {command.intent.value} {target}"
        return (
            ConfirmationSpec(
                target,
                f'Review plugin {target}. Type "{phrase}".',
                phrase,
                f"cancel plugin operation {target}",
            ),
            fingerprint,
            revalidator,
        )

    def _execute(self, command: UserCommand) -> str:
        intent = command.intent
        if intent is IntentType.LIST_PLUGINS:
            items = self.manager.discover()
            return (
                "No plugins discovered."
                if not items
                else "\n".join(
                    f"{item.manifest.plugin_id}: {item.status.value}" for item in items
                )
            )
        if intent is IntentType.VALIDATE_PLUGIN_PACKAGE:
            manifest = self.manager.installer.validate(
                Path(self._required(command, "plugin_package_path"))
            )
            return f"Plugin package {manifest.plugin_id} is structurally valid."
        if intent is IntentType.INSTALL_PLUGIN:
            installed = self.manager.install(
                Path(self._required(command, "plugin_package_path"))
            )
            return f"Installed plugin {installed.manifest.plugin_id} in disabled state."
        reference = self._required(command, "plugin_reference")
        metadata = self.manager.select(reference)
        if intent is IntentType.SHOW_PLUGIN:
            return (
                f"{metadata.manifest.display_name} {metadata.manifest.version}: "
                f"{metadata.status.value}."
            )
        if intent is IntentType.SHOW_PLUGIN_PERMISSIONS:
            approved = self.manager.permissions.approved(
                reference, str(metadata.manifest.version), metadata.fingerprint
            )
            return "Approved permissions: " + (
                ", ".join(sorted(value.value for value in approved)) or "none"
            )
        if intent is IntentType.GRANT_PLUGIN_PERMISSION:
            self.manager.grant(
                PluginPermission(self._required(command, "plugin_permission"))
            )
            return "Plugin permission granted for this exact version and fingerprint."
        if intent is IntentType.REVOKE_PLUGIN_PERMISSION:
            self.manager.revoke(
                PluginPermission(self._required(command, "plugin_permission"))
            )
            return "Plugin permission revoked."
        if intent is IntentType.ENABLE_PLUGIN:
            self.manager.enable()
            return f"Enabled plugin {reference}."
        if intent is IntentType.DISABLE_PLUGIN:
            self.manager.disable()
            return f"Disabled plugin {reference}."
        if intent is IntentType.REMOVE_PLUGIN:
            self.manager.remove()
            return f"Removed installed plugin {reference}."
        if intent is IntentType.RELOAD_PLUGIN:
            self.manager.disable()
            self.manager.enable()
            self.manager.activate()
            return f"Reloaded plugin {reference}."
        return "No failed plugin metadata is available."

    @staticmethod
    def _required(command: UserCommand, name: str) -> str:
        value = next(
            (
                entity.value
                for entity in command.entities
                if entity.name == name and isinstance(entity.value, str)
            ),
            None,
        )
        if not value:
            raise PluginError(f"{name} is required.")
        return value

    @staticmethod
    def _redacted(command: UserCommand) -> UserCommand:
        text = f"[plugin command: {command.intent.value}]"
        return UserCommand(
            text,
            command_id=command.command_id,
            normalized_text=text,
            intent=command.intent,
            confidence=command.confidence,
            received_at=command.received_at,
            source=command.source,
            session_id=command.session_id,
            metadata={"privacy_redacted": True},
        )

    @staticmethod
    def _failure(command: UserCommand, action: Action, message: str) -> ActionResult:
        safe = message[:500] or "Plugin operation failed safely."
        details = OmegaErrorDetails(
            "PLUGIN_OPERATION_FAILED",
            ErrorCategory.EXECUTION,
            "Plugin operation failed safely.",
            safe,
            True,
            details={"private_values_omitted": True},
            action_id=action.action_id,
            command_id=command.command_id,
        )
        return ActionResult.failure_result(
            action.action_id, "Plugin operation failed safely.", safe, details
        )
