"""Privacy-first email proposals routed through Omega's central gateway."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from omega.email import (
    EmailAddress,
    EmailDraft,
    EmailError,
    EmailMessage,
    EmailProviderError,
    EmailProviderTimeout,
    EmailSearchQuery,
    EmailService,
    EmailValidationError,
)
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
from omega.models._serialization import JsonValue
from omega.safety import (
    ConfirmationSpec,
    GatewayDispatchResult,
    ResourceFingerprint,
    SafeExecutionGateway,
    SafetyContext,
)
from omega.understanding.result import CommandParseResult

_READ = frozenset(
    {
        IntentType.EMAIL_STATUS,
        IntentType.LIST_EMAILS,
        IntentType.LIST_UNREAD_EMAILS,
        IntentType.SEARCH_EMAILS,
        IntentType.READ_EMAIL,
        IntentType.SUMMARIZE_EMAIL,
        IntentType.LIST_EMAIL_DRAFTS,
        IntentType.SHOW_EMAIL_ATTACHMENTS,
    }
)
_DRAFT = frozenset(
    {
        IntentType.CREATE_EMAIL_DRAFT,
        IntentType.CREATE_EMAIL_REPLY_DRAFT,
        IntentType.UPDATE_EMAIL_DRAFT,
    }
)
_MUTATION = frozenset({IntentType.SEND_EMAIL_DRAFT, IntentType.ARCHIVE_EMAIL})
_HANDLED = _READ | _DRAFT | _MUTATION


@dataclass(frozen=True)
class EmailDispatchResult:
    command: UserCommand
    action: Action
    result: ActionResult

    @property
    def user_message(self) -> str:
        return self.result.user_message

    @classmethod
    def from_gateway(cls, value: GatewayDispatchResult) -> EmailDispatchResult:
        return cls(value.command, value.action, value.result)


class EmailActionDispatcher:
    """Execute bounded email workflows without persisting sensitive command text."""

    def __init__(self, service: EmailService, gateway: SafeExecutionGateway) -> None:
        self.service = service
        self.gateway = gateway

    def dispatch(self, parsed: CommandParseResult) -> EmailDispatchResult | None:
        original = parsed.command
        if (
            not parsed.matched
            or parsed.requires_clarification
            or original.intent not in _HANDLED
        ):
            return None
        command = self._redacted_command(original)
        risk = (
            RiskLevel.HIGH
            if original.intent in _MUTATION
            else RiskLevel.MEDIUM if original.intent in _DRAFT else RiskLevel.LOW
        )
        action = Action(
            command.command_id,
            command.intent,
            parameters={
                "email_operation": command.intent.value,
                "content_persisted": False,
                "external_side_effect": command.intent in _MUTATION,
            },
            risk_level=risk,
            permission_decision=PermissionDecision.ALLOW,
            confirmation_status=ConfirmationStatus.NOT_REQUIRED,
            requires_confirmation=False,
        )
        session_id = original.session_id or UUID(int=0)
        target: EmailDraft | EmailMessage | None = None
        try:
            if original.intent is IntentType.SEND_EMAIL_DRAFT:
                target = self.service.select_draft(
                    session_id, self._number(original, "draft_reference")
                )
            elif original.intent is IntentType.ARCHIVE_EMAIL:
                target = self.service.read_message(session_id)
        except EmailError as error:
            return self._preparation_failure(command, action, error)
        context = SafetyContext(
            command,
            action,
            session_id,
            logical_source=(
                target.draft_id
                if isinstance(target, EmailDraft)
                else (
                    target.message_id
                    if isinstance(target, EmailMessage)
                    else command.intent.value
                )
            ),
            target_type=(
                "email_draft" if isinstance(target, EmailDraft) else "email_message"
            ),
            target_exists=target is not None if original.intent in _MUTATION else None,
            additional_context={
                "email_body_persisted": False,
                "credentials_present": False,
                "bulk_operation": False,
                "permanent_delete": False,
            },
        )
        confirmation = self._confirmation(original.intent, target)
        fingerprint = self._fingerprint(target)
        value = self.gateway.submit(
            context,
            lambda: self._execute(original, action),
            confirmation=confirmation,
            fingerprint=fingerprint,
            revalidator=lambda: self._revalidate(original.intent, session_id, target),
        )
        return EmailDispatchResult.from_gateway(value)

    def clear_session(self, session_id: UUID | None) -> None:
        self.service.clear_session(session_id)

    def _execute(self, command: UserCommand, action: Action) -> ActionResult:
        try:
            return self._execute_validated(command, action)
        except EmailProviderTimeout:
            return self._failure(
                command,
                action,
                "EMAIL_PROVIDER_TIMEOUT_AMBIGUOUS",
                "The email provider timed out. Delivery status is uncertain, so "
                "Omega will not retry this draft automatically.",
                ErrorCategory.TIMEOUT,
            )
        except EmailProviderError:
            return self._failure(
                command,
                action,
                "EMAIL_PROVIDER_FAILED",
                "The email provider could not complete the request. Sensitive "
                "provider details were omitted.",
                ErrorCategory.EXECUTION,
            )
        except EmailError as error:
            return self._failure(
                command,
                action,
                "EMAIL_OPERATION_FAILED",
                str(error),
                ErrorCategory.EXECUTION,
            )
        except Exception as error:
            return self._failure(
                command,
                action,
                "EMAIL_PROVIDER_RESPONSE_INVALID",
                "The email provider returned an invalid response. No sensitive "
                "details were exposed.",
                ErrorCategory.INTERNAL,
                diagnostic=type(error).__name__,
            )

    def _execute_validated(self, command: UserCommand, action: Action) -> ActionResult:
        session_id = command.session_id or UUID(int=0)
        intent = command.intent
        if intent is IntentType.EMAIL_STATUS:
            return self._success(
                action, "Email status checked.", self.service.status(), {}
            )
        if intent in {IntentType.LIST_EMAILS, IntentType.LIST_UNREAD_EMAILS}:
            page = self.service.list_messages(
                session_id, unread_only=intent is IntentType.LIST_UNREAD_EMAILS
            )
            lines = [
                f"{index}. {item.sender} — {item.subject or '(no subject)'} — "
                f"{item.received_at.isoformat()} — "
                f"{'unread' if item.unread else 'read'}"
                f"{' — attachments' if item.has_attachments else ''}"
                for index, item in enumerate(page.items, 1)
            ]
            return self._success(
                action,
                "Email summaries listed.",
                "\n".join(lines) or "No matching emails were found.",
                {"count": len(page.items)},
            )
        if intent is IntentType.SEARCH_EMAILS:
            query = self._query(command)
            page = self.service.search(session_id, query)
            lines = [
                f"{index}. {item.sender} — {item.subject or '(no subject)'} — "
                f"{item.received_at.isoformat()}"
                for index, item in enumerate(page.items, 1)
            ]
            return self._success(
                action,
                "Email search completed.",
                "\n".join(lines) or "No matching emails were found.",
                {"count": len(page.items)},
            )
        if intent is IntentType.READ_EMAIL:
            message = self.service.read_message(
                session_id, self._number(command, "email_reference")
            )
            attachment_lines = "\n".join(
                f"- {item.filename} ({item.mime_type}, {item.size_bytes} bytes)"
                for item in message.attachments
            )
            display = (
                f"From: {message.sender}\n"
                f"To: {', '.join(str(item) for item in message.recipients)}\n"
                f"Subject: {message.subject or '(no subject)'}\n"
                f"Received: {message.received_at.isoformat()}\n\n"
                f"{message.plain_text_body or '(no plain-text body)'}"
                + (f"\n\nAttachments:\n{attachment_lines}" if attachment_lines else "")
            )
            return self._success(
                action,
                "Email read.",
                display,
                {"message_id": message.message_id, "body_persisted": False},
            )
        if intent is IntentType.SUMMARIZE_EMAIL:
            return self._success(
                action,
                "Deterministic email summary prepared.",
                self.service.summarize(session_id),
                {"local_deterministic": True},
            )
        if intent is IntentType.SHOW_EMAIL_ATTACHMENTS:
            attachment_items = self.service.attachment_metadata(session_id)
            display = "\n".join(
                f"{index}. {item.filename} — {item.mime_type} — {item.size_bytes} bytes"
                for index, item in enumerate(attachment_items, 1)
            )
            return self._success(
                action,
                "Attachment metadata listed.",
                display or "This email has no attachments.",
                {"count": len(attachment_items), "downloaded": False},
            )
        if intent is IntentType.CREATE_EMAIL_DRAFT:
            recipient = EmailAddress(self._required_text(command, "email_recipient"))
            draft = self.service.create_draft(
                session_id, (recipient,), self._text(command, "email_subject") or "", ""
            )
            return self._draft_result(
                action, draft, "Email draft created. It has not been sent."
            )
        if intent is IntentType.CREATE_EMAIL_REPLY_DRAFT:
            draft = self.service.create_reply_draft(session_id)
            return self._draft_result(
                action, draft, "Reply draft created. It has not been sent."
            )
        if intent is IntentType.UPDATE_EMAIL_DRAFT:
            draft = self.service.update_draft(
                session_id,
                subject=self._text(command, "draft_subject"),
                body=self._text(command, "draft_body"),
            )
            return self._draft_result(
                action, draft, "Email draft updated. It has not been sent."
            )
        if intent is IntentType.LIST_EMAIL_DRAFTS:
            drafts = self.service.list_drafts(session_id)
            display = "\n".join(
                f"{index}. To: {', '.join(str(item) for item in draft.recipients)}"
                f" — Subject: {draft.subject or '(no subject)'}"
                for index, draft in enumerate(drafts, 1)
            )
            return self._success(
                action,
                "Email drafts listed.",
                display or "No email drafts were found.",
                {"count": len(drafts)},
            )
        if intent is IntentType.SEND_EMAIL_DRAFT:
            outcome = self.service.send_selected_draft(
                session_id, str(action.action_id)
            )
            return self._success(
                action,
                "Confirmed email draft sent.",
                "The confirmed draft was sent once.",
                {"operation_id": outcome.operation_id, "status": outcome.status.value},
            )
        if intent is IntentType.ARCHIVE_EMAIL:
            outcome = self.service.archive_selected_message(
                session_id, str(action.action_id)
            )
            return self._success(
                action,
                "Confirmed email archived.",
                "The selected email was archived. It was not deleted.",
                {
                    "operation_id": outcome.operation_id,
                    "status": outcome.status.value,
                    "permanent_delete": False,
                },
            )
        raise EmailValidationError("That email operation is unavailable.")

    def _query(self, command: UserCommand) -> EmailSearchQuery:
        sender = self._text(command, "email_sender")
        return EmailSearchQuery(
            text=self._text(command, "email_query"),
            sender=EmailAddress(sender) if sender else None,
            subject=self._text(command, "email_subject_query"),
            limit=self.service.configuration.maximum_messages_per_request,
        )

    @staticmethod
    def _confirmation(
        intent: IntentType, target: EmailDraft | EmailMessage | None
    ) -> ConfirmationSpec | None:
        if intent is IntentType.SEND_EMAIL_DRAFT and isinstance(target, EmailDraft):
            phrase = f"confirm send draft {target.draft_id}"
            review = (
                f"To: {', '.join(str(item) for item in target.recipients)}\n"
                f"Subject: {target.subject or '(no subject)'}\n"
                f"Body:\n{target.body or '(empty)'}"
            )
            return ConfirmationSpec(
                target.draft_id,
                f"Review this draft before sending:\n{review}\n"
                f'Type "{phrase}" to send it once.',
                phrase,
                f"cancel send draft {target.draft_id}",
            )
        if intent is IntentType.ARCHIVE_EMAIL and isinstance(target, EmailMessage):
            phrase = f"confirm archive email {target.message_id}"
            return ConfirmationSpec(
                target.message_id,
                "Archive the selected email with subject "
                f"{target.subject or '(no subject)'}? Type \"{phrase}\".",
                phrase,
                f"cancel archive email {target.message_id}",
            )
        return None

    def _revalidate(
        self,
        intent: IntentType,
        session_id: UUID,
        target: EmailDraft | EmailMessage | None,
    ) -> ResourceFingerprint | None:
        try:
            if intent is IntentType.SEND_EMAIL_DRAFT and isinstance(target, EmailDraft):
                current = self.service.selected_draft(session_id)
                return self._fingerprint(current)
            if intent is IntentType.ARCHIVE_EMAIL and isinstance(target, EmailMessage):
                current_message = self.service.read_message(session_id)
                return self._fingerprint(current_message)
        except EmailError:
            return ResourceFingerprint("email", "missing", False)
        return None

    @staticmethod
    def _fingerprint(
        target: EmailDraft | EmailMessage | None,
    ) -> ResourceFingerprint | None:
        if isinstance(target, EmailDraft):
            return ResourceFingerprint(
                "email_draft",
                f"{target.draft_id}:{target.updated_at.isoformat()}",
                True,
            )
        if isinstance(target, EmailMessage):
            return ResourceFingerprint("email_message", target.message_id, True)
        return None

    @staticmethod
    def _redacted_command(command: UserCommand) -> UserCommand:
        text = f"[email command: {command.intent.value}]"
        return UserCommand(
            text,
            command_id=command.command_id,
            normalized_text=text,
            intent=command.intent,
            entities=[],
            confidence=command.confidence,
            received_at=command.received_at,
            source=command.source,
            session_id=command.session_id,
            metadata={"privacy_redacted": True, "email_content_persisted": False},
        )

    @staticmethod
    def _text(command: UserCommand, name: str) -> str | None:
        for item in command.entities:
            if item.name == name and isinstance(item.value, str):
                return item.value
        return None

    @classmethod
    def _required_text(cls, command: UserCommand, name: str) -> str:
        value = cls._text(command, name)
        if value is None:
            raise EmailValidationError(f"{name} is required.")
        return value

    @staticmethod
    def _number(command: UserCommand, name: str) -> int | None:
        for item in command.entities:
            if (
                item.name == name
                and isinstance(item.value, int)
                and not isinstance(item.value, bool)
            ):
                return item.value
        return None

    @staticmethod
    def _success(
        action: Action, message: str, user_message: str, data: dict[str, JsonValue]
    ) -> ActionResult:
        return ActionResult.success_result(
            action.action_id, message, user_message, data=data
        )

    @classmethod
    def _draft_result(
        cls, action: Action, draft: EmailDraft, message: str
    ) -> ActionResult:
        display = (
            f"To: {', '.join(str(item) for item in draft.recipients)}\n"
            f"Subject: {draft.subject or '(no subject)'}\n"
            f"Body:\n{draft.body or '(empty)'}\n\n{message}"
        )
        return cls._success(
            action,
            "Reviewable email draft prepared.",
            display,
            {
                "draft_id": draft.draft_id,
                "sent": False,
                "body_persisted_in_history": False,
            },
        )

    @staticmethod
    def _failure(
        command: UserCommand,
        action: Action,
        code: str,
        user_message: str,
        category: ErrorCategory,
        *,
        diagnostic: str = "Email operation failed safely.",
    ) -> ActionResult:
        details = OmegaErrorDetails(
            code,
            category,
            diagnostic,
            user_message,
            True,
            details={"sensitive_details_omitted": True},
            action_id=action.action_id,
            command_id=command.command_id,
        )
        return ActionResult.failure_result(
            action.action_id, diagnostic, user_message, details
        )

    @classmethod
    def _preparation_failure(
        cls, command: UserCommand, action: Action, error: EmailError
    ) -> EmailDispatchResult:
        return EmailDispatchResult(
            command,
            action,
            cls._failure(
                command,
                action,
                "EMAIL_SELECTION_INVALID",
                str(error),
                ErrorCategory.VALIDATION,
            ),
        )
