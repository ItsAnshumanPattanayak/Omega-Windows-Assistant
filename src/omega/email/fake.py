"""Deterministic in-memory provider used only for tests and safe demos."""

from __future__ import annotations

from dataclasses import replace
from threading import RLock

from omega.email.exceptions import EmailNotFoundError, EmailProviderTimeout
from omega.email.models import (
    AttachmentMetadata,
    DraftStatus,
    EmailDraft,
    EmailMessage,
    EmailPage,
    EmailSearchQuery,
    ProviderCapabilities,
    utc_now,
)


class FakeEmailProvider:
    """A zero-network provider with observable mutation counters."""

    def __init__(self, messages: tuple[EmailMessage, ...] = ()) -> None:
        self._messages = {item.message_id: item for item in messages}
        self._drafts: dict[str, EmailDraft] = {}
        self._archived: set[str] = set()
        self._operations: dict[str, str] = {}
        self._lock = RLock()
        self.send_count = 0
        self.archive_count = 0
        self.network_operations = 0
        self.timeout_next_send = False

    @property
    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities()

    def list_messages(self, *, limit: int, unread_only: bool = False) -> EmailPage:
        items = [
            item
            for item in self._messages.values()
            if item.message_id not in self._archived
            and (not unread_only or item.unread)
        ]
        items.sort(key=lambda item: item.received_at, reverse=True)
        return EmailPage(tuple(item.summary() for item in items[:limit]), limit)

    def search_messages(self, query: EmailSearchQuery) -> EmailPage:
        def matches(item: EmailMessage) -> bool:
            if item.message_id in self._archived:
                return False
            if query.text:
                needle = query.text.casefold()
                if needle not in f"{item.subject} {item.plain_text_body}".casefold():
                    return False
            if query.sender and item.sender != query.sender:
                return False
            if query.recipient and query.recipient not in item.recipients:
                return False
            if (
                query.subject
                and query.subject.casefold() not in item.subject.casefold()
            ):
                return False
            if query.unread is not None and item.unread is not query.unread:
                return False
            if (
                query.has_attachment is not None
                and bool(item.attachments) is not query.has_attachment
            ):
                return False
            if query.start_at and item.received_at < query.start_at:
                return False
            return not query.end_at or item.received_at <= query.end_at

        items = sorted(
            (item for item in self._messages.values() if matches(item)),
            key=lambda item: item.received_at,
            reverse=True,
        )[: query.limit]
        return EmailPage(tuple(item.summary() for item in items), query.limit)

    def read_message(self, message_id: str) -> EmailMessage:
        try:
            return self._messages[message_id]
        except KeyError as error:
            raise EmailNotFoundError(
                "The selected email is no longer available."
            ) from error

    def create_draft(self, draft: EmailDraft) -> EmailDraft:
        with self._lock:
            self._drafts[draft.draft_id] = draft
        return draft

    def update_draft(self, draft: EmailDraft) -> EmailDraft:
        with self._lock:
            if draft.draft_id not in self._drafts:
                raise EmailNotFoundError("The selected draft is no longer available.")
            self._drafts[draft.draft_id] = draft
        return draft

    def list_drafts(self, *, limit: int) -> tuple[EmailDraft, ...]:
        drafts = sorted(
            self._drafts.values(), key=lambda item: item.updated_at, reverse=True
        )
        return tuple(item for item in drafts if item.status is DraftStatus.DRAFT)[
            :limit
        ]

    def send_draft(self, draft_id: str, operation_id: str) -> str:
        with self._lock:
            if operation_id in self._operations:
                return self._operations[operation_id]
            if draft_id not in self._drafts:
                raise EmailNotFoundError("The selected draft is no longer available.")
            if self.timeout_next_send:
                self.timeout_next_send = False
                raise EmailProviderTimeout(
                    "The provider timed out; delivery status is intentionally treated "
                    "as ambiguous."
                )
            reference = f"sent-{draft_id}"
            self._drafts[draft_id] = replace(
                self._drafts[draft_id], status=DraftStatus.SENT, updated_at=utc_now()
            )
            self._operations[operation_id] = reference
            self.send_count += 1
            return reference

    def archive_message(self, message_id: str, operation_id: str) -> str:
        with self._lock:
            if operation_id in self._operations:
                return self._operations[operation_id]
            if message_id not in self._messages:
                raise EmailNotFoundError("The selected email is no longer available.")
            self._archived.add(message_id)
            reference = f"archived-{message_id}"
            self._operations[operation_id] = reference
            self.archive_count += 1
            return reference

    def attachment_metadata(self, message_id: str) -> tuple[AttachmentMetadata, ...]:
        return self.read_message(message_id).attachments
