"""Safety-gated command adapter for explicit personalization changes."""

from __future__ import annotations

from dataclasses import dataclass
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
from omega.personalization import (
    PersonalizationError,
    PreferenceCategory,
    PreferenceService,
    ProfileExportService,
    ProfileImportService,
)
from omega.safety import ConfirmationSpec, SafeExecutionGateway, SafetyContext
from omega.understanding.result import CommandParseResult

_INTENTS = frozenset(
    {
        IntentType.SHOW_PROFILE,
        IntentType.SHOW_PREFERENCES,
        IntentType.SHOW_PRIVACY_PREFERENCES,
        IntentType.SHOW_REMEMBERED_PREFERENCES,
        IntentType.SET_PREFERENCE,
        IntentType.SET_SESSION_PREFERENCE,
        IntentType.RESET_SESSION_PREFERENCES,
        IntentType.RESET_PREFERENCE_CATEGORY,
        IntentType.RESET_ALL_PREFERENCES,
        IntentType.EXPORT_PROFILE,
        IntentType.IMPORT_PROFILE,
        IntentType.CREATE_PROFILE,
        IntentType.SWITCH_PROFILE,
        IntentType.LIST_PROFILES,
        IntentType.DELETE_PROFILE,
    }
)
_CONFIRMATION_INTENTS = frozenset(
    {
        IntentType.RESET_ALL_PREFERENCES,
        IntentType.IMPORT_PROFILE,
        IntentType.DELETE_PROFILE,
    }
)


@dataclass(frozen=True)
class PreferenceDispatchResult:
    command: UserCommand
    action: Action
    result: ActionResult
    display_message: str

    @property
    def user_message(self) -> str:
        return self.display_message


class PreferenceDispatcher:
    def __init__(
        self,
        service: PreferenceService,
        exporter: ProfileExportService,
        importer: ProfileImportService,
        gateway: SafeExecutionGateway,
    ) -> None:
        self.service, self.exporter, self.importer, self.gateway = (
            service,
            exporter,
            importer,
            gateway,
        )

    def dispatch(self, parsed: CommandParseResult) -> PreferenceDispatchResult | None:
        command = parsed.command
        if (
            not parsed.matched
            or parsed.requires_clarification
            or command.intent not in _INTENTS
        ):
            return None
        confirmation = command.intent in _CONFIRMATION_INTENTS
        action = Action(
            command.command_id,
            command.intent,
            parameters={"preference_operation": command.intent.value},
            risk_level=RiskLevel.MEDIUM if confirmation else RiskLevel.LOW,
            permission_decision=(
                PermissionDecision.REQUIRE_CONFIRMATION
                if confirmation
                else PermissionDecision.ALLOW
            ),
            confirmation_status=(
                ConfirmationStatus.PENDING
                if confirmation
                else ConfirmationStatus.NOT_REQUIRED
            ),
            requires_confirmation=confirmation,
            metadata={"preference_values_omitted": True},
        )
        safe_command = UserCommand(
            f"[{command.intent.value}]",
            normalized_text=command.intent.value,
            intent=command.intent,
            confidence=command.confidence,
            source=command.source,
            session_id=command.session_id,
            command_id=command.command_id,
            received_at=command.received_at,
            metadata={"private_preference_values_omitted": True},
        )
        display = ""

        def execute() -> ActionResult:
            nonlocal display
            try:
                display = self._execute(command)
                return ActionResult.success_result(
                    action.action_id,
                    "The personalization request completed.",
                    "The personalization request completed; private values were "
                    "omitted from history.",
                    metadata={"preference_values_omitted": True},
                )
            except PersonalizationError as error:
                display = str(error)
                details = OmegaErrorDetails(
                    "PERSONALIZATION_REQUEST_FAILED",
                    ErrorCategory.VALIDATION,
                    type(error).__name__,
                    display,
                    True,
                    action_id=action.action_id,
                    command_id=command.command_id,
                )
                return ActionResult.failure_result(
                    action.action_id,
                    "The personalization request failed safely.",
                    display,
                    details,
                )

        confirmation_spec = None
        if confirmation:
            confirmation_spec = ConfirmationSpec(
                "personalization profile",
                "This broad personalization change requires exact confirmation.",
                f"confirm preference change {action.action_id.hex[:8]}",
                f"cancel preference change {action.action_id.hex[:8]}",
            )
        submitted = self.gateway.submit(
            SafetyContext(
                safe_command,
                action,
                command.session_id,
                logical_source=command.intent.value,
                target_type="personalization",
                additional_context={
                    "private_values_omitted": True,
                    "shell_like": False,
                },
            ),
            execute,
            confirmation=confirmation_spec,
        )
        return PreferenceDispatchResult(
            submitted.command,
            submitted.action,
            submitted.result,
            display or submitted.user_message,
        )

    def clear_session(self, session_id: UUID | None) -> None:
        if session_id is not None:
            self.service.resolver.clear_session(session_id)

    def _execute(self, command: UserCommand) -> str:
        intent = command.intent
        if intent is IntentType.SHOW_PROFILE:
            return (
                f"Active profile: {self.service.active_profile.name}. "
                f"{self.service.remembered_summary()}"
            )
        if intent in {IntentType.SHOW_PREFERENCES, IntentType.SHOW_PRIVACY_PREFERENCES}:
            values = self.service.list_preferences()
            if intent is IntentType.SHOW_PRIVACY_PREFERENCES:
                values = tuple(
                    item
                    for item in values
                    if item.category is PreferenceCategory.PRIVACY
                )
            return (
                "No explicit preferences are stored."
                if not values
                else "Stored preference keys: "
                + ", ".join(item.key for item in values)
                + "."
            )
        if intent is IntentType.SHOW_REMEMBERED_PREFERENCES:
            return self.service.remembered_summary()
        if intent in {IntentType.SET_PREFERENCE, IntentType.SET_SESSION_PREFERENCE}:
            result = self.service.set_preference(
                self._entity(command, "preference_key"),
                self._raw_entity(command, "preference_value"),
                session_id=command.session_id,
                temporary=intent is IntentType.SET_SESSION_PREFERENCE,
            )
            return result.message
        if intent is IntentType.RESET_SESSION_PREFERENCES:
            return (
                "There are no active session preferences."
                if command.session_id is None
                else self.service.reset_session(command.session_id).message
            )
        if intent is IntentType.RESET_PREFERENCE_CATEGORY:
            return self.service.reset_category(
                PreferenceCategory(self._entity(command, "preference_category"))
            ).message
        if intent is IntentType.RESET_ALL_PREFERENCES:
            return self.service.reset_all(confirmed=True).message
        if intent is IntentType.EXPORT_PROFILE:
            return "Profile export preview:\n" + self.exporter.export_json()
        if intent is IntentType.IMPORT_PROFILE:
            return (
                "Profile import requires a validated GUI preview and typed "
                "confirmation; no file was read."
            )
        if intent is IntentType.CREATE_PROFILE:
            name = self._entity(command, "profile_name")
            return f"Created profile {self.service.create_profile(name).name}."
        if intent is IntentType.SWITCH_PROFILE:
            name = self._entity(command, "profile_name")
            profile = self.service.switch_profile(name)
            if command.session_id is not None:
                self.service.resolver.clear_session(command.session_id)
            return f"Active profile: {profile.name}. Session preferences were cleared."
        if intent is IntentType.LIST_PROFILES:
            return (
                "Profiles: "
                + ", ".join(
                    item.name for item in self.service.repository.list_profiles()
                )
                + "."
            )
        if intent is IntentType.DELETE_PROFILE:
            self.service.delete_profile(
                self._entity(command, "profile_name"), confirmed=True
            )
            return (
                "The selected profile was deleted; unrelated Omega data was unchanged."
            )
        raise PersonalizationError("That personalization operation is unsupported.")

    @staticmethod
    def _raw_entity(command: UserCommand, name: str) -> object:
        for entity in command.entities:
            if entity.name == name:
                return entity.value
        raise PersonalizationError("The preference value is missing.")

    @staticmethod
    def _entity(command: UserCommand, name: str) -> str:
        value = PreferenceDispatcher._raw_entity(command, name)
        if not isinstance(value, str) or not value.strip():
            raise PersonalizationError("The personalization request is incomplete.")
        return value
