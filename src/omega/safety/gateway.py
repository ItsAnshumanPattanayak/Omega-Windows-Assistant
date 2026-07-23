"""The only production gateway from typed action proposals to domain executors."""

from __future__ import annotations

import hashlib
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from threading import RLock
from uuid import UUID

from omega.database.lifecycle import ExecutionPersistence
from omega.models import (
    Action,
    ActionResult,
    ActionStatus,
    CommandSource,
    ConfirmationStatus,
    ErrorCategory,
    OmegaErrorDetails,
    PermissionDecision,
    UserCommand,
)
from omega.models._serialization import utc_now
from omega.safety.audit import (
    InMemorySafetyAudit,
    SafetyAuditEvent,
    SafetyAuditRecord,
)
from omega.safety.confirmations import (
    ConfirmationManager,
    ConfirmationOutcome,
    Executor,
    Revalidator,
)
from omega.safety.messages import EXPIRED_CONFIRMATION, RESOURCE_CHANGED
from omega.safety.models import ResourceFingerprint, SafetyContext, SafetyEvaluation
from omega.safety.permissions import PermissionPolicyEngine


@dataclass(frozen=True)
class ConfirmationSpec:
    """Safe display and exact-command scope for one high-risk action."""

    display_target: str
    prompt: str
    expected_confirmation: str
    expected_cancellation: str


@dataclass(frozen=True)
class GatewayDispatchResult:
    command: UserCommand
    action: Action
    result: ActionResult
    evaluation: SafetyEvaluation | None = None

    @property
    def user_message(self) -> str:
        return self.result.user_message


class SafeExecutionGateway:
    """Classify, authorize, confirm, revalidate, audit, and dispatch once."""

    def __init__(
        self,
        *,
        policy_engine: PermissionPolicyEngine | None = None,
        confirmations: ConfirmationManager | None = None,
        audit: InMemorySafetyAudit | None = None,
        persistence: ExecutionPersistence | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        self.policy_engine = policy_engine or PermissionPolicyEngine()
        self.confirmations = confirmations or ConfirmationManager()
        self.audit = audit or InMemorySafetyAudit()
        self.persistence = persistence
        self._logger = logger or logging.getLogger("omega.safety.gateway")
        self._executed_actions: set[UUID] = set()
        self._execution_lock = RLock()

    def submit(
        self,
        context: SafetyContext,
        executor: Executor,
        *,
        confirmation: ConfirmationSpec | None = None,
        revalidator: Revalidator = lambda: None,
        fingerprint: ResourceFingerprint | None = None,
    ) -> GatewayDispatchResult:
        """Evaluate one typed proposal and never dispatch a denied action."""
        if self.persistence is not None:
            try:
                self.persistence.record_proposal(context.command, context.action)
            except Exception:
                self._logger.exception("Execution proposal persistence failed closed.")
                return GatewayDispatchResult(
                    context.command,
                    context.action,
                    self._failure(
                        context.action,
                        context.command,
                        "PERSISTENCE_FAILED_CLOSED",
                        "The execution proposal could not be persisted.",
                        "Omega could not record that operation safely, so nothing "
                        "was changed.",
                        ErrorCategory.INTERNAL,
                    ),
                )
        prompt = confirmation.prompt if confirmation else None
        try:
            evaluation = self.policy_engine.evaluate(
                context, confirmation_prompt=prompt
            )
        except Exception:
            self._logger.exception("Safety evaluation failed closed.")
            self._set_denied(context.action)
            result = self._failure(
                context.action,
                context.command,
                "SAFETY_EVALUATION_FAILED",
                "Safety evaluation failed closed.",
                "Omega could not verify that operation safely, so nothing "
                "was changed.",
            )
            self._persist_terminal(context.action, result)
            return GatewayDispatchResult(
                context.command,
                context.action,
                result,
            )
        self._audit(SafetyAuditEvent.EVALUATED, context, evaluation)
        if evaluation.decision is PermissionDecision.DENY:
            self._set_denied(context.action)
            self._audit(SafetyAuditEvent.DENIED, context, evaluation)
            result = self._failure(
                context.action,
                context.command,
                evaluation.reason_code,
                evaluation.reason,
                evaluation.user_message,
            )
            self._persist_terminal(context.action, result)
            return GatewayDispatchResult(
                context.command,
                context.action,
                result,
                evaluation,
            )
        if evaluation.decision is PermissionDecision.REQUIRE_CONFIRMATION:
            if confirmation is None or context.session_id is None:
                self._set_denied(context.action)
                return GatewayDispatchResult(
                    context.command,
                    context.action,
                    self._failure(
                        context.action,
                        context.command,
                        "CONFIRMATION_CONTEXT_MISSING",
                        "A scoped session confirmation could not be created.",
                        "Omega could not create a safe confirmation request.",
                    ),
                    evaluation,
                )
            self._set_awaiting(context.action)
            if self.persistence is not None:
                try:
                    self.persistence.update_action(context.action)
                except Exception:
                    self._logger.exception(
                        "Pending confirmation persistence failed closed."
                    )
                    self._set_denied(context.action)
                    return GatewayDispatchResult(
                        context.command,
                        context.action,
                        self._failure(
                            context.action,
                            context.command,
                            "PERSISTENCE_FAILED_CLOSED",
                            "Pending action state could not be persisted.",
                            "Omega could not record that confirmation safely.",
                            ErrorCategory.INTERNAL,
                        ),
                        evaluation,
                    )
            pending, replaced = self.confirmations.create(
                session_id=context.session_id,
                command=context.command,
                action=context.action,
                display_target=confirmation.display_target,
                prompt=confirmation.prompt,
                expected_confirmation=confirmation.expected_confirmation,
                expected_cancellation=confirmation.expected_cancellation,
                fingerprint=fingerprint,
                executor=executor,
                revalidator=revalidator,
                context=context,
            )
            self._audit(
                SafetyAuditEvent.CONFIRMATION_CREATED,
                context,
                evaluation,
                ConfirmationStatus.PENDING,
            )
            replacement = (
                " The previous pending confirmation was cancelled."
                if replaced is not None
                else ""
            )
            return GatewayDispatchResult(
                context.command,
                context.action,
                self._failure(
                    context.action,
                    context.command,
                    "CONFIRMATION_REQUIRED",
                    evaluation.reason,
                    f"{confirmation.prompt}{replacement}",
                    ErrorCategory.PERMISSION,
                    recoverable=True,
                ),
                evaluation,
            )
        self._set_allowed(context.action)
        if self.persistence is not None:
            try:
                self.persistence.update_action(context.action)
            except Exception:
                self._logger.exception("Approved action persistence failed closed.")
                return GatewayDispatchResult(
                    context.command,
                    context.action,
                    self._failure(
                        context.action,
                        context.command,
                        "PERSISTENCE_FAILED_CLOSED",
                        "Approved action state could not be persisted.",
                        "Omega could not record that operation safely, so nothing "
                        "was changed.",
                        ErrorCategory.INTERNAL,
                    ),
                    evaluation,
                )
        self._audit(SafetyAuditEvent.ALLOWED, context, evaluation)
        result = self._execute_once(
            context.command,
            context.action,
            executor,
            revalidator,
            fingerprint,
            context,
            evaluation,
        )
        return GatewayDispatchResult(
            context.command, context.action, result, evaluation
        )

    def handle_confirmation(
        self, text: str, session_id: UUID | None
    ) -> GatewayDispatchResult | None:
        """Resolve one exact process-local control phrase without raw execution."""
        match = self.confirmations.resolve(text, session_id)
        if match.outcome is ConfirmationOutcome.NOT_HANDLED:
            return None
        command = UserCommand(
            text,
            normalized_text=" ".join(text.strip().casefold().split()),
            intent=match.action.intent if match.action else UserCommand(text).intent,
            source=CommandSource.TEXT,
            session_id=session_id,
        )
        if self.persistence is not None:
            try:
                self.persistence.record_command(command)
            except Exception:
                self._logger.exception("Confirmation command persistence failed.")
                return None
        if match.action is None:
            action = Action(
                command_id=command.command_id,
                intent=command.intent,
                permission_decision=PermissionDecision.DENY,
                confirmation_status=ConfirmationStatus.NOT_REQUIRED,
                requires_confirmation=False,
                status=ActionStatus.REJECTED,
            )
        else:
            action = match.action
        if match.outcome is ConfirmationOutcome.APPROVED:
            assert match.executor is not None and match.revalidator is not None
            action.status = ActionStatus.APPROVED
            action.confirmation_status = ConfirmationStatus.APPROVED
            context = match.context or SafetyContext(
                command=match.command or command,
                action=action,
                session_id=session_id,
                logical_source=(
                    match.pending.display_target if match.pending else None
                ),
            )
            evaluation = self.policy_engine.evaluate(
                context, confirmation_prompt="approved"
            )
            if evaluation.decision is PermissionDecision.DENY:
                self._set_denied(action)
                self._audit(SafetyAuditEvent.DENIED, context, evaluation)
                return GatewayDispatchResult(
                    command,
                    action,
                    self._failure(
                        action,
                        command,
                        evaluation.reason_code,
                        evaluation.reason,
                        evaluation.user_message,
                    ),
                    evaluation,
                )
            self._audit(
                SafetyAuditEvent.CONFIRMATION_APPROVED,
                context,
                evaluation,
                ConfirmationStatus.APPROVED,
            )
            result = self._execute_once(
                match.command or command,
                action,
                match.executor,
                match.revalidator,
                match.original_fingerprint,
                context,
                evaluation,
            )
            return GatewayDispatchResult(command, action, result, evaluation)
        messages = {
            ConfirmationOutcome.CANCELLED: "The pending operation was cancelled.",
            ConfirmationOutcome.EXPIRED: EXPIRED_CONFIRMATION,
            ConfirmationOutcome.MISMATCH: "I don't understand that command yet.",
            ConfirmationOutcome.ATTEMPTS_EXCEEDED: (
                "The confirmation request was cancelled after too many invalid "
                "attempts. Please give the original command again."
            ),
            ConfirmationOutcome.SESSION_MISMATCH: (
                "That confirmation belongs to a different session and was not "
                "accepted."
            ),
            ConfirmationOutcome.REPLAYED: (
                "There is no pending confirmation for that command."
            ),
        }
        code = {
            ConfirmationOutcome.CANCELLED: "CONFIRMATION_CANCELLED",
            ConfirmationOutcome.EXPIRED: "CONFIRMATION_EXPIRED",
            ConfirmationOutcome.MISMATCH: "CONFIRMATION_MISMATCH",
            ConfirmationOutcome.ATTEMPTS_EXCEEDED: "CONFIRMATION_ATTEMPTS_EXCEEDED",
            ConfirmationOutcome.SESSION_MISMATCH: "CONFIRMATION_SESSION_MISMATCH",
            ConfirmationOutcome.REPLAYED: "CONFIRMATION_REPLAY_BLOCKED",
        }[match.outcome]
        if match.outcome in {
            ConfirmationOutcome.CANCELLED,
            ConfirmationOutcome.ATTEMPTS_EXCEEDED,
            ConfirmationOutcome.EXPIRED,
        }:
            action.status = ActionStatus.CANCELLED
            action.confirmation_status = (
                ConfirmationStatus.EXPIRED
                if match.outcome is ConfirmationOutcome.EXPIRED
                else ConfirmationStatus.REJECTED
            )
        return GatewayDispatchResult(
            command,
            action,
            self._failure(
                action,
                command,
                code,
                code.replace("_", " ").title(),
                messages[match.outcome],
                (
                    ErrorCategory.CANCELLED
                    if match.outcome is ConfirmationOutcome.CANCELLED
                    else ErrorCategory.PERMISSION
                ),
                recoverable=True,
            ),
        )

    def clear_confirmations(self, session_id: UUID | None = None) -> None:
        self.confirmations.clear(session_id)

    def handle_unrecognized(
        self, command: UserCommand, session_id: UUID | None
    ) -> GatewayDispatchResult | None:
        """Deny shell-like unknown text instead of letting it reach a manager."""
        shell_like = bool(
            re.search(r"(?:&&|\|\||[|;<>`]|\$\()", command.original_text)
            or command.original_text.strip()
            .casefold()
            .startswith(("run ", "execute ", "open cmd /", "open powershell -"))
        )
        path_match = re.search(
            r"(?:[A-Za-z]:\\[^\r\n]+|\\\\[^\r\n]+)",
            command.original_text,
        )
        if not shell_like and path_match is None:
            return None
        action = Action(
            command_id=command.command_id,
            intent=command.intent,
            parameters={},
            permission_decision=PermissionDecision.ALLOW,
            confirmation_status=ConfirmationStatus.NOT_REQUIRED,
            requires_confirmation=False,
        )
        context = SafetyContext(
            command=command,
            action=action,
            session_id=session_id,
            destination_path=Path(path_match.group(0)) if path_match else None,
            additional_context={"shell_like": shell_like},
        )
        return self.submit(
            context,
            lambda: self._unreachable_unknown(action.action_id),
        )

    @staticmethod
    def _unreachable_unknown(action_id: UUID) -> ActionResult:
        raise RuntimeError(f"Denied unknown action reached executor {action_id}.")

    def _execute_once(
        self,
        command: UserCommand,
        action: Action,
        executor: Executor,
        revalidator: Revalidator,
        fingerprint: ResourceFingerprint | None,
        context: SafetyContext,
        evaluation: SafetyEvaluation,
    ) -> ActionResult:
        with self._execution_lock:
            if action.action_id in self._executed_actions:
                return self._failure(
                    action,
                    command,
                    "DUPLICATE_EXECUTION_BLOCKED",
                    "The action was already consumed.",
                    "That action has already been handled and will not run again.",
                )
            self._executed_actions.add(action.action_id)
        try:
            current = revalidator()
            if fingerprint is not None and current != fingerprint:
                action.status = ActionStatus.CANCELLED
                self._audit(SafetyAuditEvent.RESOURCE_CHANGED, context, evaluation)
                return self._failure(
                    action,
                    command,
                    "RESOURCE_CHANGED",
                    "Resource fingerprint changed before dispatch.",
                    RESOURCE_CHANGED,
                    ErrorCategory.SAFETY,
                )
            action.status = ActionStatus.RUNNING
            action.started_at = utc_now()
            if self.persistence is not None:
                try:
                    self.persistence.update_action(action)
                except Exception:
                    self._logger.exception("Pre-execution persistence failed closed.")
                    action.status = ActionStatus.FAILED
                    action.completed_at = utc_now()
                    return self._failure(
                        action,
                        command,
                        "PERSISTENCE_FAILED_CLOSED",
                        "Running action state could not be persisted.",
                        "Omega could not record that operation safely, so nothing "
                        "was changed.",
                        ErrorCategory.INTERNAL,
                    )
            self._audit(SafetyAuditEvent.EXECUTION_STARTED, context, evaluation)
            result = executor()
            action.status = (
                ActionStatus.SUCCEEDED if result.success else ActionStatus.FAILED
            )
            action.completed_at = utc_now()
            self._audit(SafetyAuditEvent.EXECUTION_FINISHED, context, evaluation)
            if self.persistence is not None:
                try:
                    self.persistence.record_terminal(action, result)
                except Exception:
                    self._logger.exception("Post-execution result persistence failed.")
                    return self._failure(
                        action,
                        command,
                        "RESULT_PERSISTENCE_FAILED",
                        "The completed operation result could not be persisted.",
                        "The operation completed, but Omega could not save its "
                        "result. It will not be repeated automatically.",
                        ErrorCategory.INTERNAL,
                    )
            return result
        except Exception:
            action.status = ActionStatus.FAILED
            action.completed_at = utc_now()
            self._logger.exception("Approved domain execution failed safely.")
            failure = self._failure(
                action,
                command,
                "EXECUTION_FAILED_SAFE",
                "An approved executor raised an unexpected exception.",
                "Omega could not complete that operation safely.",
                ErrorCategory.INTERNAL,
            )
            self._persist_terminal(action, failure)
            return failure

    def _persist_terminal(self, action: Action, result: ActionResult) -> None:
        if self.persistence is None:
            return
        try:
            self.persistence.record_terminal(action, result)
        except Exception:
            self._logger.exception("Terminal safety result persistence failed.")

    @staticmethod
    def fingerprint_path(
        path: Path, *, maximum_hash_bytes: int = 1_048_576
    ) -> ResourceFingerprint:
        """Capture bounded file/folder state without retaining file content."""
        resolved = path.resolve(strict=False)
        identifier = hashlib.sha256(
            str(resolved).casefold().encode("utf-8")
        ).hexdigest()
        if not path.exists():
            return ResourceFingerprint("path", identifier, False)
        stat = path.stat()
        if path.is_file():
            digest = None
            if stat.st_size <= maximum_hash_bytes:
                digest = hashlib.sha256(path.read_bytes()).hexdigest()
            return ResourceFingerprint(
                "file", identifier, True, stat.st_size, stat.st_mtime_ns, digest=digest
            )
        if path.is_dir():
            count = sum(1 for _ in path.iterdir())
            return ResourceFingerprint(
                "folder",
                identifier,
                True,
                modified_ns=stat.st_mtime_ns,
                item_count=count,
            )
        return ResourceFingerprint(
            "other", identifier, True, modified_ns=stat.st_mtime_ns
        )

    def _audit(
        self,
        event: SafetyAuditEvent,
        context: SafetyContext,
        evaluation: SafetyEvaluation,
        confirmation_status: ConfirmationStatus = ConfirmationStatus.NOT_REQUIRED,
    ) -> None:
        target = (
            context.logical_destination
            or context.logical_source
            or context.application_id
            or "approved target"
        )
        self.audit.append(
            SafetyAuditRecord(
                event=event,
                session_id=context.session_id,
                command_id=context.command.command_id,
                action_id=context.action.action_id,
                intent=context.action.intent,
                risk_level=evaluation.risk_level,
                decision=evaluation.decision,
                reason_code=evaluation.reason_code,
                policy_ids=evaluation.matched_policies,
                confirmation_status=confirmation_status,
                safe_target_description=target,
            )
        )

    @staticmethod
    def _set_denied(action: Action) -> None:
        action.permission_decision = PermissionDecision.DENY
        action.requires_confirmation = False
        action.confirmation_status = ConfirmationStatus.NOT_REQUIRED
        action.status = ActionStatus.REJECTED

    @staticmethod
    def _set_awaiting(action: Action) -> None:
        action.permission_decision = PermissionDecision.REQUIRE_CONFIRMATION
        action.requires_confirmation = True
        action.confirmation_status = ConfirmationStatus.PENDING
        action.status = ActionStatus.AWAITING_CONFIRMATION

    @staticmethod
    def _set_allowed(action: Action) -> None:
        action.permission_decision = PermissionDecision.ALLOW
        action.requires_confirmation = False
        action.confirmation_status = ConfirmationStatus.NOT_REQUIRED
        action.status = ActionStatus.APPROVED

    @staticmethod
    def _failure(
        action: Action,
        command: UserCommand,
        code: str,
        message: str,
        user_message: str,
        category: ErrorCategory = ErrorCategory.SAFETY,
        *,
        recoverable: bool = False,
    ) -> ActionResult:
        error = OmegaErrorDetails(
            code=code,
            category=category,
            message=message,
            user_message=user_message,
            recoverable=recoverable,
            action_id=action.action_id,
            command_id=command.command_id,
        )
        return ActionResult.failure_result(
            action.action_id, message, user_message, error
        )
