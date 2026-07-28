"""Local-AI commands routed through safety with content-minimized receipts."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from omega.ai import AiError, AiService
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
from omega.safety import SafeExecutionGateway, SafetyContext
from omega.understanding.result import CommandParseResult

_INTENTS = frozenset(
    {
        IntentType.SHOW_LOCAL_AI_STATUS,
        IntentType.LIST_LOCAL_AI_MODELS,
        IntentType.LOAD_LOCAL_AI_MODEL,
        IntentType.UNLOAD_LOCAL_AI_MODEL,
        IntentType.ASK_LOCAL_AI,
        IntentType.SUMMARIZE_TEXT_WITH_AI,
        IntentType.CANCEL_AI_GENERATION,
        IntentType.CLEAR_AI_CONVERSATION,
        IntentType.SHOW_AI_CONTEXT_STATUS,
        IntentType.START_AI_CONVERSATION,
    }
)
_RESOURCE_INTENTS = {
    IntentType.LOAD_LOCAL_AI_MODEL,
    IntentType.UNLOAD_LOCAL_AI_MODEL,
}


@dataclass(frozen=True)
class AiDispatchResult:
    command: UserCommand
    action: Action
    result: ActionResult
    display_message: str

    @property
    def user_message(self) -> str:
        return self.display_message


class AiDispatcher:
    """Dispatch proposals only; generated text never becomes another command."""

    def __init__(self, service: AiService, gateway: SafeExecutionGateway) -> None:
        self.service = service
        self.gateway = gateway

    def dispatch(self, parsed: CommandParseResult) -> AiDispatchResult | None:
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
            parameters={"ai_operation": command.intent.value},
            risk_level=(
                RiskLevel.MEDIUM
                if command.intent in _RESOURCE_INTENTS
                else RiskLevel.LOW
            ),
            permission_decision=PermissionDecision.ALLOW,
            confirmation_status=ConfirmationStatus.NOT_REQUIRED,
            requires_confirmation=False,
            metadata={"generated_content_omitted": True},
        )
        safe_command = UserCommand(
            f"[{command.intent.value}]",
            normalized_text=command.intent.value,
            intent=command.intent,
            entities=[],
            confidence=command.confidence,
            source=command.source,
            session_id=command.session_id,
            command_id=command.command_id,
            received_at=command.received_at,
            metadata={"private_ai_input_omitted": True},
        )
        display = ""

        def execute() -> ActionResult:
            nonlocal display
            try:
                display = self._execute(command)
                return ActionResult.success_result(
                    action.action_id,
                    "The bounded local-AI request completed.",
                    "The local-AI request completed; generated content was omitted "
                    "from persistent history.",
                    metadata={"generated_content_omitted": True},
                )
            except AiError as error:
                display = str(error)
                details = OmegaErrorDetails(
                    "LOCAL_AI_REQUEST_FAILED",
                    ErrorCategory.EXECUTION,
                    type(error).__name__,
                    display,
                    True,
                    action_id=action.action_id,
                    command_id=command.command_id,
                )
                return ActionResult.failure_result(
                    action.action_id,
                    "The bounded local-AI request failed safely.",
                    display,
                    details,
                    metadata={"private_ai_content_omitted": True},
                )

        submitted = self.gateway.submit(
            SafetyContext(
                safe_command,
                action,
                command.session_id,
                logical_source=command.intent.value,
                target_type="local_ai",
                additional_context={
                    "shell_like": False,
                    "generated_action_dispatch": False,
                    "private_content_omitted": True,
                },
            ),
            execute,
        )
        if not display:
            display = submitted.user_message
        return AiDispatchResult(
            submitted.command, submitted.action, submitted.result, display
        )

    def clear_session(self, session_id: UUID | None) -> None:
        self.service.clear_context(session_id)

    def _execute(self, command: UserCommand) -> str:
        intent = command.intent
        if intent is IntentType.SHOW_LOCAL_AI_STATUS:
            status = self.service.status()
            loaded_names = ", ".join(status.loaded_models) or "none"
            return f"{status.message} Loaded models: {loaded_names}."
        if intent is IntentType.LIST_LOCAL_AI_MODELS:
            descriptors = self.service.list_models()
            if not descriptors:
                return "No local AI models are explicitly configured."
            return "\n".join(
                f"{model.model_id}: {model.status.value} "
                f"({', '.join(sorted(item.value for item in model.capabilities))})"
                for model in descriptors
            )
        if intent is IntentType.LOAD_LOCAL_AI_MODEL:
            if command.source.value == "voice":
                return "Model loading must be requested with typed input."
            model_id = self._entity(command, "ai_model")
            self.service.load_model(model_id)
            return f"Local AI model {model_id} is loaded."
        if intent is IntentType.UNLOAD_LOCAL_AI_MODEL:
            unload_id = self._optional_entity(command, "ai_model")
            self.service.unload_model(unload_id)
            return "The selected local AI model is unloaded."
        if intent is IntentType.ASK_LOCAL_AI:
            result = self.service.generate(
                "local_question",
                self._entity(command, "ai_request"),
                session_id=command.session_id,
            )
            return self._format(result.model_id, result.text, result.warning)
        if intent is IntentType.SUMMARIZE_TEXT_WITH_AI:
            result = self.service.summarize(
                self._entity(command, "ai_text"), session_id=command.session_id
            )
            label = result.model_id or "deterministic fallback"
            return self._format(label, result.text, result.warning)
        if intent is IntentType.CANCEL_AI_GENERATION:
            count = self.service.cancel()
            return f"Cancellation requested for {count} active AI request(s)."
        if intent in {
            IntentType.CLEAR_AI_CONVERSATION,
            IntentType.START_AI_CONVERSATION,
        }:
            self.service.clear_context(command.session_id)
            return "The session-local AI conversation context is clear."
        if intent is IntentType.SHOW_AI_CONTEXT_STATUS:
            if command.session_id is None:
                return "There is no active AI conversation context."
            turns, characters = self.service.context_status(command.session_id)
            return f"AI context: {turns} bounded item(s), {characters} character(s)."
        raise AiError("That local-AI operation is unsupported.")

    @staticmethod
    def _entity(command: UserCommand, name: str) -> str:
        value = AiDispatcher._optional_entity(command, name)
        if value is None or not value.strip():
            raise AiError("The local-AI request is missing required text.")
        return value

    @staticmethod
    def _optional_entity(command: UserCommand, name: str) -> str | None:
        for entity in command.entities:
            if entity.name == name and isinstance(entity.value, str):
                return entity.value
        return None

    @staticmethod
    def _format(model: str | None, text: str, warning: str) -> str:
        return f"Local AI ({model or 'unavailable'}):\n{text}\n\nWarning: {warning}"
