"""Provider-independent email workflows with bounded session selection."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from threading import RLock
from uuid import UUID, uuid4

from omega.email.configuration import EmailConfiguration
from omega.email.exceptions import (
    DuplicateEmailOperationError,
    EmailNotFoundError,
    EmailProviderTimeout,
    EmailUnavailableError,
    EmailValidationError,
)
from omega.email.models import (
    AttachmentMetadata,
    EmailAddress,
    EmailDraft,
    EmailMessage,
    EmailOperationOutcome,
    EmailOperationStatus,
    EmailPage,
    EmailSearchQuery,
)
from omega.email.protocols import EmailProvider
from omega.email.repository import EmailOperationStore, InMemoryEmailOperationStore
from omega.email.summary import DeterministicEmailSummarizer


@dataclass
class _SessionSelection:
    message_ids: tuple[str, ...] = ()
    current_message_id: str | None = None
    draft_ids: tuple[str, ...] = ()
    current_draft_id: str | None = None


class EmailService:
    """Coordinate validation, provider calls, selection, and mutation receipts."""

    def __init__(
        self,
        configuration: EmailConfiguration,
        provider: EmailProvider | None = None,
        operation_store: EmailOperationStore | None = None,
    ) -> None:
        self.configuration = configuration
        self.provider = provider
        self.operation_store = operation_store or InMemoryEmailOperationStore()
        self.summarizer = DeterministicEmailSummarizer(
            configuration.maximum_summary_characters
        )
        self._selections: dict[UUID, _SessionSelection] = {}
        self._lock = RLock()

    @property
    def available(self) -> bool:
        return self.configuration.enabled and self.provider is not None

    def status(self) -> str:
        if not self.configuration.enabled:
            return "Email assistance is disabled."
        if self.provider is None:
            return "Email assistance is enabled but no provider is configured."
        return (
            f"Email assistance is connected to account profile {self._account_name()}."
        )

    def list_messages(
        self, session_id: UUID, *, unread_only: bool = False
    ) -> EmailPage:
        provider = self._provider()
        page = provider.list_messages(
            limit=self.configuration.maximum_messages_per_request,
            unread_only=unread_only,
        )
        self._validate_page(page)
        with self._lock:
            selection = self._selections.setdefault(session_id, _SessionSelection())
            selection.message_ids = tuple(item.message_id for item in page.items)
            selection.current_message_id = None
        return page

    def search(self, session_id: UUID, query: EmailSearchQuery) -> EmailPage:
        if (
            query.text
            and len(query.text) > self.configuration.maximum_search_query_characters
        ):
            raise EmailValidationError(
                "Email search query exceeds the configured limit."
            )
        provider = self._provider()
        bounded = EmailSearchQuery(
            text=query.text,
            sender=query.sender,
            recipient=query.recipient,
            subject=query.subject,
            unread=query.unread,
            has_attachment=query.has_attachment,
            start_at=query.start_at,
            end_at=query.end_at,
            limit=min(query.limit, self.configuration.maximum_messages_per_request),
        )
        page = provider.search_messages(bounded)
        self._validate_page(page)
        with self._lock:
            selection = self._selections.setdefault(session_id, _SessionSelection())
            selection.message_ids = tuple(item.message_id for item in page.items)
            selection.current_message_id = None
        return page

    def read_message(
        self, session_id: UUID, reference: int | None = None
    ) -> EmailMessage:
        message_id = self.resolve_message_id(session_id, reference)
        message = self._provider().read_message(message_id)
        if len(message.plain_text_body) > self.configuration.maximum_body_characters:
            maximum = self.configuration.maximum_body_characters
            message = EmailMessage(
                message.message_id,
                message.thread_id,
                message.sender,
                message.recipients,
                message.subject,
                message.received_at,
                message.plain_text_body[: max(0, maximum - 1)] + "…",
                message.html_available,
                message.labels,
                message.attachments,
                message.unread,
            )
        with self._lock:
            self._selections[session_id].current_message_id = message_id
        return message

    def resolve_message_id(self, session_id: UUID, reference: int | None = None) -> str:
        selection = self._selections.get(session_id)
        if selection is None:
            raise EmailNotFoundError("List or search emails before selecting one.")
        if reference is None:
            if selection.current_message_id is None:
                raise EmailNotFoundError("Open a selected email first.")
            return selection.current_message_id
        if (
            isinstance(reference, bool)
            or reference < 1
            or reference > len(selection.message_ids)
        ):
            raise EmailNotFoundError(
                "That email number is not in the current result set."
            )
        return selection.message_ids[reference - 1]

    def summarize(self, session_id: UUID) -> str:
        return self.summarizer.summarize(self.read_message(session_id))

    def attachment_metadata(self, session_id: UUID) -> tuple[AttachmentMetadata, ...]:
        message_id = self.resolve_message_id(session_id)
        attachments = self._provider().attachment_metadata(message_id)
        if len(attachments) > 100:
            raise EmailValidationError(
                "Provider returned excessive attachment metadata."
            )
        for item in attachments:
            if item.size_bytes > self.configuration.maximum_attachment_bytes:
                raise EmailValidationError(
                    "An attachment exceeds the configured metadata size limit."
                )
        return attachments

    def create_draft(
        self,
        session_id: UUID,
        recipients: tuple[EmailAddress, ...],
        subject: str = "",
        body: str = "",
        *,
        reply_to_message_id: str | None = None,
    ) -> EmailDraft:
        self._validate_draft_fields(recipients, subject, body)
        now = datetime.now(UTC)
        draft = EmailDraft(
            f"draft-{uuid4().hex}",
            recipients,
            subject,
            body,
            now,
            now,
            reply_to_message_id,
        )
        created = self._provider().create_draft(draft)
        with self._lock:
            selection = self._selections.setdefault(session_id, _SessionSelection())
            selection.draft_ids = (created.draft_id,)
            selection.current_draft_id = created.draft_id
        return created

    def create_reply_draft(self, session_id: UUID) -> EmailDraft:
        message = self.read_message(session_id)
        subject = (
            message.subject
            if message.subject.casefold().startswith("re:")
            else f"Re: {message.subject}"
        )
        return self.create_draft(
            session_id,
            (message.sender,),
            subject,
            "",
            reply_to_message_id=message.message_id,
        )

    def update_draft(
        self, session_id: UUID, *, subject: str | None = None, body: str | None = None
    ) -> EmailDraft:
        draft = self.selected_draft(session_id)
        candidate = draft.updated(subject=subject, body=body, at=datetime.now(UTC))
        self._validate_draft_fields(
            candidate.recipients, candidate.subject, candidate.body
        )
        return self._provider().update_draft(candidate)

    def list_drafts(self, session_id: UUID) -> tuple[EmailDraft, ...]:
        drafts = self._provider().list_drafts(
            limit=self.configuration.maximum_messages_per_request
        )
        with self._lock:
            selection = self._selections.setdefault(session_id, _SessionSelection())
            selection.draft_ids = tuple(item.draft_id for item in drafts)
            selection.current_draft_id = (
                drafts[0].draft_id if len(drafts) == 1 else None
            )
        return drafts

    def select_draft(self, session_id: UUID, reference: int | None) -> EmailDraft:
        drafts = self._provider().list_drafts(
            limit=self.configuration.maximum_messages_per_request
        )
        by_id = {item.draft_id: item for item in drafts}
        selection = self._selections.get(session_id)
        if selection is None:
            raise EmailNotFoundError("Create or list drafts before selecting one.")
        draft_id = selection.current_draft_id
        if reference is not None:
            if reference < 1 or reference > len(selection.draft_ids):
                raise EmailNotFoundError(
                    "That draft number is not in the current draft list."
                )
            draft_id = selection.draft_ids[reference - 1]
            selection.current_draft_id = draft_id
        if draft_id is None or draft_id not in by_id:
            raise EmailNotFoundError("Select an exact draft before sending.")
        return by_id[draft_id]

    def selected_draft(self, session_id: UUID) -> EmailDraft:
        return self.select_draft(session_id, None)

    def send_selected_draft(
        self, session_id: UUID, operation_id: str
    ) -> EmailOperationOutcome:
        selection = self._selections.get(session_id)
        draft_id = selection.current_draft_id if selection is not None else None
        if draft_id is None:
            raise EmailNotFoundError("Select an exact draft before sending.")
        if not self.operation_store.claim(
            operation_id, self._account_name(), "send", draft_id
        ):
            raise DuplicateEmailOperationError(
                "This draft already has a send attempt and will not be sent again."
            )
        try:
            reference = self._provider().send_draft(draft_id, operation_id)
        except EmailProviderTimeout:
            self.operation_store.finish(operation_id, EmailOperationStatus.AMBIGUOUS)
            raise
        except Exception:
            self.operation_store.finish(operation_id, EmailOperationStatus.FAILED)
            raise
        self.operation_store.finish(
            operation_id, EmailOperationStatus.SUCCEEDED, reference
        )
        return EmailOperationOutcome(
            operation_id, EmailOperationStatus.SUCCEEDED, reference
        )

    def archive_selected_message(
        self, session_id: UUID, operation_id: str
    ) -> EmailOperationOutcome:
        message_id = self.resolve_message_id(session_id)
        if not self.operation_store.claim(
            operation_id, self._account_name(), "archive", message_id
        ):
            raise DuplicateEmailOperationError(
                "This email already has an archive attempt."
            )
        try:
            reference = self._provider().archive_message(message_id, operation_id)
        except Exception:
            self.operation_store.finish(operation_id, EmailOperationStatus.AMBIGUOUS)
            raise
        self.operation_store.finish(
            operation_id, EmailOperationStatus.SUCCEEDED, reference
        )
        self._selections[session_id].current_message_id = None
        return EmailOperationOutcome(
            operation_id, EmailOperationStatus.SUCCEEDED, reference
        )

    def clear_session(self, session_id: UUID | None) -> None:
        if session_id is not None:
            self._selections.pop(session_id, None)

    def _provider(self) -> EmailProvider:
        if not self.configuration.enabled:
            raise EmailUnavailableError(
                "Email assistance is disabled in configuration."
            )
        if self.provider is None:
            raise EmailUnavailableError("No email provider is configured.")
        return self.provider

    def _account_name(self) -> str:
        return self.configuration.account_name or "default"

    def _validate_page(self, page: EmailPage) -> None:
        if len(page.items) > self.configuration.maximum_messages_per_request:
            raise EmailValidationError("Provider returned too many messages.")

    def _validate_draft_fields(
        self, recipients: tuple[EmailAddress, ...], subject: str, body: str
    ) -> None:
        if len(recipients) > self.configuration.maximum_recipients:
            raise EmailValidationError(
                "Draft recipient count exceeds the configured limit."
            )
        if len(subject) > self.configuration.maximum_subject_characters:
            raise EmailValidationError("Draft subject exceeds the configured limit.")
        if "\r" in subject or "\n" in subject:
            raise EmailValidationError(
                "Draft subject must not contain header newlines."
            )
        if len(body) > self.configuration.maximum_draft_body_characters:
            raise EmailValidationError("Draft body exceeds the configured limit.")
