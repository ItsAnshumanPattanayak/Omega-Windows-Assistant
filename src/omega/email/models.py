"""Validated provider-independent email domain records."""

from __future__ import annotations

import re
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from enum import StrEnum

from omega.email.exceptions import EmailValidationError
from omega.models._serialization import JsonValue

_ADDRESS_RE = re.compile(
    r"^[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@"
    r"(?:[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?\.)+"
    r"[A-Za-z]{2,63}$"
)
_IDENTIFIER_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:@/+\-=]{0,254}$")


class DraftStatus(StrEnum):
    DRAFT = "draft"
    SENT = "sent"


class EmailOperationStatus(StrEnum):
    PENDING = "pending"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    AMBIGUOUS = "ambiguous"


def _text(value: object, name: str, maximum: int, *, empty: bool = False) -> str:
    if not isinstance(value, str):
        raise EmailValidationError(f"{name} must be text.")
    if "\r" in value or "\n" in value and name in {"subject", "identifier"}:
        raise EmailValidationError(f"{name} must not contain header newlines.")
    if not empty and not value.strip():
        raise EmailValidationError(f"{name} must not be empty.")
    if len(value) > maximum:
        raise EmailValidationError(f"{name} exceeds {maximum} characters.")
    return value


def _identifier(value: str, name: str = "identifier") -> str:
    value = _text(value, name, 255)
    if not _IDENTIFIER_RE.fullmatch(value):
        raise EmailValidationError(f"{name} has an invalid shape.")
    return value


def _timestamp(value: datetime, name: str) -> datetime:
    if (
        not isinstance(value, datetime)
        or value.tzinfo is None
        or value.utcoffset() is None
    ):
        raise EmailValidationError(f"{name} must be timezone-aware.")
    return value.astimezone(UTC)


@dataclass(frozen=True)
class EmailAddress:
    """One normalized mailbox address with no display-name or header syntax."""

    value: str

    def __post_init__(self) -> None:
        raw = _text(self.value, "email address", 254)
        if not _ADDRESS_RE.fullmatch(raw) or ".." in raw:
            raise EmailValidationError("Email address is malformed.")
        local, domain = raw.rsplit("@", 1)
        object.__setattr__(self, "value", f"{local}@{domain.casefold()}")

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True)
class AttachmentMetadata:
    attachment_id: str
    filename: str
    mime_type: str
    size_bytes: int

    def __post_init__(self) -> None:
        _identifier(self.attachment_id, "attachment_id")
        filename = _text(self.filename, "filename", 255)
        if (
            filename in {".", ".."}
            or "/" in filename
            or "\\" in filename
            or "\x00" in filename
        ):
            raise EmailValidationError("Attachment filename is unsafe.")
        mime = _text(self.mime_type, "mime_type", 127)
        if not re.fullmatch(r"[A-Za-z0-9!#$&^_.+-]+/[A-Za-z0-9!#$&^_.+-]+", mime):
            raise EmailValidationError("Attachment MIME type is malformed.")
        if (
            isinstance(self.size_bytes, bool)
            or not isinstance(self.size_bytes, int)
            or self.size_bytes < 0
        ):
            raise EmailValidationError("Attachment size must be non-negative.")

    def to_dict(self) -> dict[str, JsonValue]:
        return {
            "attachment_id": self.attachment_id,
            "filename": self.filename,
            "mime_type": self.mime_type,
            "size_bytes": self.size_bytes,
        }


@dataclass(frozen=True)
class EmailMessageSummary:
    message_id: str
    thread_id: str | None
    sender: EmailAddress
    subject: str
    received_at: datetime
    snippet: str
    unread: bool
    has_attachments: bool

    def __post_init__(self) -> None:
        if not isinstance(self.sender, EmailAddress):
            raise EmailValidationError("Message sender must be an EmailAddress.")
        _identifier(self.message_id, "message_id")
        if self.thread_id is not None:
            _identifier(self.thread_id, "thread_id")
        _text(self.subject, "subject", 998, empty=True)
        _text(self.snippet, "snippet", 500, empty=True)
        object.__setattr__(
            self, "received_at", _timestamp(self.received_at, "received_at")
        )
        if not isinstance(self.unread, bool) or not isinstance(
            self.has_attachments, bool
        ):
            raise EmailValidationError("Message flags must be booleans.")

    def to_dict(self) -> dict[str, JsonValue]:
        return {
            "message_id": self.message_id,
            "thread_id": self.thread_id,
            "sender": str(self.sender),
            "subject": self.subject,
            "received_at": self.received_at.isoformat(),
            "snippet": self.snippet,
            "unread": self.unread,
            "has_attachments": self.has_attachments,
        }


@dataclass(frozen=True)
class EmailMessage:
    message_id: str
    thread_id: str | None
    sender: EmailAddress
    recipients: tuple[EmailAddress, ...]
    subject: str
    received_at: datetime
    plain_text_body: str
    html_available: bool = False
    labels: tuple[str, ...] = ()
    attachments: tuple[AttachmentMetadata, ...] = ()
    unread: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.sender, EmailAddress) or not all(
            isinstance(item, EmailAddress) for item in self.recipients
        ):
            raise EmailValidationError("Message addresses are invalid.")
        if not all(isinstance(item, AttachmentMetadata) for item in self.attachments):
            raise EmailValidationError("Message attachment metadata is invalid.")
        if not all(isinstance(item, str) and item.strip() for item in self.labels):
            raise EmailValidationError("Message labels must be non-empty text.")
        _identifier(self.message_id, "message_id")
        if self.thread_id is not None:
            _identifier(self.thread_id, "thread_id")
        if not self.recipients:
            raise EmailValidationError("A message must have at least one recipient.")
        if len(self.recipients) > 100 or len(self.attachments) > 100:
            raise EmailValidationError(
                "Message recipient or attachment count is excessive."
            )
        _text(self.subject, "subject", 998, empty=True)
        _text(self.plain_text_body, "message body", 1_000_000, empty=True)
        object.__setattr__(
            self, "received_at", _timestamp(self.received_at, "received_at")
        )
        if not isinstance(self.html_available, bool) or not isinstance(
            self.unread, bool
        ):
            raise EmailValidationError("Message flags must be booleans.")

    def summary(self, maximum_snippet: int = 200) -> EmailMessageSummary:
        clean = " ".join(self.plain_text_body.split())[:maximum_snippet]
        return EmailMessageSummary(
            self.message_id,
            self.thread_id,
            self.sender,
            self.subject,
            self.received_at,
            clean,
            self.unread,
            bool(self.attachments),
        )


@dataclass(frozen=True)
class EmailDraft:
    draft_id: str
    recipients: tuple[EmailAddress, ...]
    subject: str
    body: str
    created_at: datetime
    updated_at: datetime
    reply_to_message_id: str | None = None
    status: DraftStatus = DraftStatus.DRAFT

    def __post_init__(self) -> None:
        if not all(isinstance(item, EmailAddress) for item in self.recipients):
            raise EmailValidationError("Draft recipients must be EmailAddress values.")
        _identifier(self.draft_id, "draft_id")
        if not self.recipients or len(self.recipients) > 50:
            raise EmailValidationError("A draft must have 1 to 50 recipients.")
        _text(self.subject, "subject", 998, empty=True)
        _text(self.body, "draft body", 500_000, empty=True)
        if self.reply_to_message_id is not None:
            _identifier(self.reply_to_message_id, "reply_to_message_id")
        object.__setattr__(
            self, "created_at", _timestamp(self.created_at, "created_at")
        )
        object.__setattr__(
            self, "updated_at", _timestamp(self.updated_at, "updated_at")
        )
        if self.updated_at < self.created_at:
            raise EmailValidationError(
                "Draft update time cannot precede creation time."
            )

    def updated(
        self, *, subject: str | None = None, body: str | None = None, at: datetime
    ) -> EmailDraft:
        return replace(
            self,
            subject=self.subject if subject is None else subject,
            body=self.body if body is None else body,
            updated_at=at,
        )

    def to_dict(self, *, include_body: bool = True) -> dict[str, JsonValue]:
        return {
            "draft_id": self.draft_id,
            "recipients": [str(item) for item in self.recipients],
            "subject": self.subject,
            "body": self.body if include_body else "[omitted]",
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "reply_to_message_id": self.reply_to_message_id,
            "status": self.status.value,
        }


@dataclass(frozen=True)
class EmailSearchQuery:
    text: str | None = None
    sender: EmailAddress | None = None
    recipient: EmailAddress | None = None
    subject: str | None = None
    unread: bool | None = None
    has_attachment: bool | None = None
    start_at: datetime | None = None
    end_at: datetime | None = None
    limit: int = 20

    def __post_init__(self) -> None:
        for name in ("unread", "has_attachment"):
            value = getattr(self, name)
            if value is not None and not isinstance(value, bool):
                raise EmailValidationError(f"{name} must be a boolean or None.")
        if self.text is not None:
            _text(self.text, "search query", 2_000)
        if self.subject is not None:
            _text(self.subject, "subject query", 998)
        if (
            isinstance(self.limit, bool)
            or not isinstance(self.limit, int)
            or not 1 <= self.limit <= 100
        ):
            raise EmailValidationError("Search limit must be between 1 and 100.")
        if self.start_at is not None:
            object.__setattr__(self, "start_at", _timestamp(self.start_at, "start_at"))
        if self.end_at is not None:
            object.__setattr__(self, "end_at", _timestamp(self.end_at, "end_at"))
        if self.start_at and self.end_at and self.end_at < self.start_at:
            raise EmailValidationError("Search end time cannot precede start time.")
        if all(
            item is None
            for item in (
                self.text,
                self.sender,
                self.recipient,
                self.subject,
                self.unread,
                self.has_attachment,
                self.start_at,
                self.end_at,
            )
        ):
            raise EmailValidationError("Search requires at least one bounded filter.")


@dataclass(frozen=True)
class EmailPage:
    items: tuple[EmailMessageSummary, ...]
    limit: int
    next_cursor: str | None = None

    def __post_init__(self) -> None:
        if not all(isinstance(item, EmailMessageSummary) for item in self.items):
            raise EmailValidationError("Page items must be email summaries.")
        if (
            isinstance(self.limit, bool)
            or not isinstance(self.limit, int)
            or not 1 <= self.limit <= 100
        ):
            raise EmailValidationError("Page limit must be between 1 and 100.")
        if len(self.items) > self.limit:
            raise EmailValidationError("Page contains more items than its limit.")
        if self.next_cursor is not None:
            _identifier(self.next_cursor, "next_cursor")


@dataclass(frozen=True)
class EmailOperationOutcome:
    operation_id: str
    status: EmailOperationStatus
    provider_reference: str | None = None

    def __post_init__(self) -> None:
        _identifier(self.operation_id, "operation_id")
        if self.provider_reference is not None:
            _identifier(self.provider_reference, "provider_reference")


@dataclass(frozen=True)
class ProviderCapabilities:
    list_messages: bool = True
    search_messages: bool = True
    drafts: bool = True
    send: bool = True
    archive: bool = True
    attachment_metadata: bool = True
    attachment_downloads: bool = False
    permanent_delete: bool = False


def utc_now() -> datetime:
    return datetime.now(UTC)
