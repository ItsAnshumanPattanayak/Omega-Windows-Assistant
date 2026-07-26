"""Privacy-minimized workflow management through the central safety gateway."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, replace
from hashlib import sha256
from uuid import UUID, uuid4

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
from omega.safety import (
    ConfirmationSpec,
    ResourceFingerprint,
    SafeExecutionGateway,
    SafetyContext,
)
from omega.understanding.result import CommandParseResult
from omega.workflows import (
    WorkflowService,
    WorkflowStatus,
    WorkflowStep,
    WorkflowStepType,
)
from omega.workflows.exceptions import WorkflowError, WorkflowValidationError

_INTENTS = frozenset(
    {
        IntentType.CREATE_WORKFLOW,
        IntentType.SAVE_WORKFLOW,
        IntentType.ADD_WORKFLOW_STEP,
        IntentType.REMOVE_WORKFLOW_STEP,
        IntentType.MOVE_WORKFLOW_STEP,
        IntentType.LIST_WORKFLOWS,
        IntentType.SHOW_WORKFLOW,
        IntentType.PREVIEW_WORKFLOW,
        IntentType.VALIDATE_WORKFLOW,
        IntentType.RUN_WORKFLOW,
        IntentType.PAUSE_WORKFLOW,
        IntentType.RESUME_WORKFLOW,
        IntentType.CANCEL_WORKFLOW,
        IntentType.DELETE_WORKFLOW,
        IntentType.SHOW_WORKFLOW_HISTORY,
        IntentType.EXPORT_WORKFLOW,
        IntentType.IMPORT_WORKFLOW,
    }
)
_CONFIRMED = {
    IntentType.SAVE_WORKFLOW,
    IntentType.RUN_WORKFLOW,
    IntentType.DELETE_WORKFLOW,
}


@dataclass(frozen=True)
class WorkflowDispatchResult:
    command: UserCommand
    action: Action
    result: ActionResult

    @property
    def user_message(self) -> str:
        return self.result.user_message


class WorkflowDispatcher:
    def __init__(self, service: WorkflowService, gateway: SafeExecutionGateway) -> None:
        self.service, self.gateway = service, gateway

    def dispatch(self, parsed: CommandParseResult) -> WorkflowDispatchResult | None:
        original = parsed.command
        if (
            not parsed.matched
            or parsed.requires_clarification
            or original.intent not in _INTENTS
        ):
            return None
        command = self._redacted(original)
        confirmed = command.intent in _CONFIRMED
        action = Action(
            command.command_id,
            command.intent,
            parameters={"workflow_operation": command.intent.value},
            risk_level=(
                RiskLevel.HIGH
                if command.intent is IntentType.DELETE_WORKFLOW
                else RiskLevel.MEDIUM
            ),
            permission_decision=PermissionDecision.ALLOW,
            confirmation_status=ConfirmationStatus.NOT_REQUIRED,
            requires_confirmation=False,
        )
        try:
            confirmation, fingerprint, revalidator = (
                self._confirmation(original) if confirmed else (None, None, None)
            )
        except WorkflowError as error:
            return WorkflowDispatchResult(
                command, action, self._failure(command, action, str(error))
            )
        context = SafetyContext(
            command,
            action,
            original.session_id or UUID(int=0),
            logical_source=command.intent.value,
            target_type="workflow",
            target_exists=command.intent is not IntentType.CREATE_WORKFLOW,
            additional_context={
                "shell_like": False,
                "bulk_operation": False,
                "workflow_scope_only": True,
            },
        )

        def executor() -> ActionResult:
            return self._execute(original, action)

        if confirmation is None or fingerprint is None or revalidator is None:
            value = self.gateway.submit(context, executor)
        else:
            value = self.gateway.submit(
                context,
                executor,
                confirmation=confirmation,
                fingerprint=fingerprint,
                revalidator=revalidator,
            )
        return WorkflowDispatchResult(value.command, value.action, value.result)

    def clear_session(self) -> None:
        self.service.clear_session()

    def _confirmation(self, command: UserCommand) -> tuple[
        ConfirmationSpec,
        ResourceFingerprint,
        Callable[[], ResourceFingerprint | None],
    ]:
        if command.intent is IntentType.SAVE_WORKFLOW:
            item = self.service.draft()
            phrase = f"confirm save workflow {item.workflow_id}"

            def revalidator() -> ResourceFingerprint | None:
                return self._fingerprint(self.service.draft())

        else:
            item = self.service.select(self._required(command))
            verb = "run" if command.intent is IntentType.RUN_WORKFLOW else "delete"
            phrase = f"confirm {verb} workflow {item.workflow_id}"

            def revalidator() -> ResourceFingerprint | None:
                return self._fingerprint(
                    self.service.repository.get(str(item.workflow_id))
                )

        return (
            ConfirmationSpec(
                str(item.workflow_id),
                f'Review workflow {item.name} version {item.version}. Type "{phrase}".',
                phrase,
                f"cancel workflow operation {item.workflow_id}",
            ),
            self._fingerprint(item),
            revalidator,
        )

    @staticmethod
    def _fingerprint(item: object) -> ResourceFingerprint:
        from omega.workflows import WorkflowDefinition

        assert isinstance(item, WorkflowDefinition)
        payload = str(item.to_dict()).encode("utf-8")
        return ResourceFingerprint(
            "workflow_definition", sha256(payload).hexdigest(), True
        )

    def _execute(self, command: UserCommand, action: Action) -> ActionResult:
        try:
            message = self._run(command)
            return ActionResult.success_result(
                action.action_id, "Workflow operation completed.", message
            )
        except WorkflowError as error:
            return self._failure(command, action, str(error))

    def _run(self, command: UserCommand) -> str:
        intent = command.intent
        if intent is IntentType.CREATE_WORKFLOW:
            item = self.service.create_draft(self._required(command))
            return (
                f"Created draft workflow {item.name}. Add reviewed allowlisted "
                "steps before saving."
            )
        if intent is IntentType.SAVE_WORKFLOW:
            item = replace(self.service.draft(), status=WorkflowStatus.ACTIVE)
            self.service.save(item)
            return f"Saved workflow {item.name} version {item.version}."
        if intent is IntentType.ADD_WORKFLOW_STEP:
            text = self._required_named(command, "workflow_step_text")
            item = self.service.add_step(self._step_from_text(text))
            return f"Added reviewed step {len(item.steps)} to draft {item.name}."
        if intent is IntentType.REMOVE_WORKFLOW_STEP:
            number = self._required_number(command, "workflow_step_number")
            item = self.service.remove_step(number)
            return f"Removed the step. Draft {item.name} has {len(item.steps)} step(s)."
        if intent is IntentType.MOVE_WORKFLOW_STEP:
            source = self._required_number(command, "workflow_step_source")
            destination = self._required_number(command, "workflow_step_destination")
            item = self.service.move_step(source, destination)
            return f"Reordered draft {item.name}; prior approval was invalidated."
        if intent is IntentType.LIST_WORKFLOWS:
            items = self.service.list()
            return (
                "\n".join(
                    f"{i}. {item.name} ({item.status.value})"
                    for i, item in enumerate(items, 1)
                )
                or "No workflows are saved."
            )
        if intent is IntentType.SHOW_WORKFLOW_HISTORY:
            runs = self.service.history()
            return (
                "\n".join(
                    f"{index}. {run.workflow_name} ({run.status.value})"
                    for index, run in enumerate(runs, 1)
                )
                or "No workflow runs are recorded."
            )
        item = (
            self.service.select(self._required(command))
            if self._text(command)
            else self.service.selected()
        )
        if intent is IntentType.SHOW_WORKFLOW:
            return (
                f"{item.name}, version {item.version}, {len(item.steps)} step(s), "
                f"status {item.status.value}."
            )
        if intent is IntentType.PREVIEW_WORKFLOW:
            plan = self.service.planner.plan(item)
            return "\n".join(
                f"{step.number}. {step.description} [{step.service}]"
                for step in plan.steps
            )
        if intent is IntentType.VALIDATE_WORKFLOW:
            result = self.service.validator.validate(item)
            return "Workflow is valid." if result.valid else "; ".join(result.errors)
        if intent is IntentType.RUN_WORKFLOW:
            run = self.service.run(item)
            return f"Workflow {item.name} finished with status {run.status.value}."
        if intent is IntentType.DELETE_WORKFLOW:
            self.service.repository.delete(item.workflow_id)
            self.service.clear_session()
            return f"Deleted workflow {item.name}."
        if intent is IntentType.CANCEL_WORKFLOW:
            self.service.executor.cancel(str(item.workflow_id))
            return "Workflow cancellation was requested."
        if intent is IntentType.PAUSE_WORKFLOW:
            self.service.executor.pause(str(item.workflow_id))
            return "Workflow pause was requested."
        if intent is IntentType.RESUME_WORKFLOW:
            run = self.service.executor.resume(item)
            self.service.runs.save(item.name, run)
            return f"Workflow resumed with status {run.status.value}."
        return (
            "Workflow history and metadata export are available through bounded "
            "service APIs."
        )

    @staticmethod
    def _text(command: UserCommand) -> str | None:
        return next(
            (
                e.value
                for e in command.entities
                if e.name == "workflow_reference" and isinstance(e.value, str)
            ),
            None,
        )

    @classmethod
    def _required(cls, command: UserCommand) -> str:
        value = cls._text(command)
        if not value:
            raise WorkflowValidationError("Workflow reference is required.")
        return value

    @staticmethod
    def _required_named(command: UserCommand, name: str) -> str:
        value = next(
            (
                entity.value
                for entity in command.entities
                if entity.name == name and isinstance(entity.value, str)
            ),
            None,
        )
        if not value:
            raise WorkflowValidationError(f"{name} is required.")
        return value

    @staticmethod
    def _required_number(command: UserCommand, name: str) -> int:
        value = next(
            (
                entity.value
                for entity in command.entities
                if entity.name == name
                and isinstance(entity.value, int)
                and not isinstance(entity.value, bool)
            ),
            None,
        )
        if value is None:
            raise WorkflowValidationError(f"{name} is required.")
        return value

    @staticmethod
    def _step_from_text(text: str) -> WorkflowStep:
        lowered = text.casefold()
        mappings = (
            ("display message ", WorkflowStepType.DISPLAY_MESSAGE, "message"),
            (
                "open application ",
                WorkflowStepType.OPEN_APPLICATION,
                "application_name",
            ),
            ("create note ", WorkflowStepType.CREATE_NOTE, "title"),
            ("search knowledge for ", WorkflowStepType.SEARCH_KNOWLEDGE, "query"),
            ("copy text ", WorkflowStepType.COPY_CLIPBOARD, "text"),
        )
        for prefix, kind, argument in mappings:
            value = text[len(prefix) :].strip()
            if lowered.startswith(prefix) and value:
                return WorkflowStep(f"step_{uuid4().hex[:12]}", kind, {argument: value})
        raise WorkflowValidationError(
            "Use an explicitly allowlisted structured workflow step."
        )

    @staticmethod
    def _redacted(command: UserCommand) -> UserCommand:
        text = f"[workflow command: {command.intent.value}]"
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
        safe = message[:500] or "Workflow operation failed safely."
        error = OmegaErrorDetails(
            "WORKFLOW_OPERATION_FAILED",
            ErrorCategory.EXECUTION,
            "Workflow operation failed safely.",
            safe,
            True,
            details={"private_values_omitted": True},
            action_id=action.action_id,
            command_id=command.command_id,
        )
        return ActionResult.failure_result(
            action.action_id, "Workflow operation failed safely.", safe, error
        )
