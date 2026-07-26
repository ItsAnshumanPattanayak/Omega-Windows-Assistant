"""Public provider-independent email assistance API."""

from omega.email.configuration import EmailConfiguration
from omega.email.exceptions import (
    DuplicateEmailOperationError,
    EmailConfigurationError,
    EmailError,
    EmailNotFoundError,
    EmailProviderError,
    EmailProviderTimeout,
    EmailUnavailableError,
    EmailValidationError,
)
from omega.email.fake import FakeEmailProvider
from omega.email.models import (
    AttachmentMetadata,
    DraftStatus,
    EmailAddress,
    EmailDraft,
    EmailMessage,
    EmailMessageSummary,
    EmailOperationOutcome,
    EmailOperationStatus,
    EmailPage,
    EmailSearchQuery,
    ProviderCapabilities,
)
from omega.email.protocols import EmailProvider
from omega.email.repository import (
    EmailOperationStore,
    InMemoryEmailOperationStore,
    SqliteEmailOperationStore,
)
from omega.email.service import EmailService
from omega.email.summary import DeterministicEmailSummarizer

__all__ = [
    "AttachmentMetadata",
    "DeterministicEmailSummarizer",
    "DraftStatus",
    "DuplicateEmailOperationError",
    "EmailAddress",
    "EmailConfiguration",
    "EmailConfigurationError",
    "EmailDraft",
    "EmailError",
    "EmailMessage",
    "EmailMessageSummary",
    "EmailNotFoundError",
    "EmailOperationOutcome",
    "EmailOperationStatus",
    "EmailOperationStore",
    "EmailPage",
    "EmailProvider",
    "EmailProviderError",
    "EmailProviderTimeout",
    "EmailSearchQuery",
    "EmailService",
    "EmailUnavailableError",
    "EmailValidationError",
    "FakeEmailProvider",
    "InMemoryEmailOperationStore",
    "ProviderCapabilities",
    "SqliteEmailOperationStore",
]
