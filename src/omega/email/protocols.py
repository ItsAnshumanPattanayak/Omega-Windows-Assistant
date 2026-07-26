"""Narrow provider boundary for email business logic."""

from __future__ import annotations

from typing import Protocol

from omega.email.models import (
    AttachmentMetadata,
    EmailDraft,
    EmailMessage,
    EmailPage,
    EmailSearchQuery,
    ProviderCapabilities,
)


class EmailProvider(Protocol):
    """Bounded mailbox operations; permanent deletion is intentionally absent."""

    @property
    def capabilities(self) -> ProviderCapabilities: ...

    def list_messages(self, *, limit: int, unread_only: bool = False) -> EmailPage: ...

    def search_messages(self, query: EmailSearchQuery) -> EmailPage: ...

    def read_message(self, message_id: str) -> EmailMessage: ...

    def create_draft(self, draft: EmailDraft) -> EmailDraft: ...

    def update_draft(self, draft: EmailDraft) -> EmailDraft: ...

    def list_drafts(self, *, limit: int) -> tuple[EmailDraft, ...]: ...

    def send_draft(self, draft_id: str, operation_id: str) -> str: ...

    def archive_message(self, message_id: str, operation_id: str) -> str: ...

    def attachment_metadata(
        self, message_id: str
    ) -> tuple[AttachmentMetadata, ...]: ...
