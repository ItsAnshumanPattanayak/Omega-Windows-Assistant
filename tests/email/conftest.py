from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from omega.email import (
    AttachmentMetadata,
    EmailAddress,
    EmailConfiguration,
    EmailMessage,
    EmailService,
    FakeEmailProvider,
)


@pytest.fixture
def messages() -> tuple[EmailMessage, ...]:
    now = datetime(2026, 7, 25, 12, 0, tzinfo=UTC)
    return (
        EmailMessage(
            "message-2",
            "thread-2",
            EmailAddress("manager@example.com"),
            (EmailAddress("anshuman@example.com"),),
            "Quarterly plan",
            now,
            "The quarterly plan is attached. Please review it by Friday. "
            "No assumptions are required.",
            True,
            ("Inbox",),
            (AttachmentMetadata("attachment-1", "plan.pdf", "application/pdf", 1024),),
            True,
        ),
        EmailMessage(
            "message-1",
            "thread-1",
            EmailAddress("friend@example.net"),
            (EmailAddress("anshuman@example.com"),),
            "Lunch",
            now - timedelta(days=1),
            "Would you like to have lunch next week?",
            False,
            ("Inbox",),
            (),
            False,
        ),
    )


@pytest.fixture
def email_configuration() -> EmailConfiguration:
    return EmailConfiguration.from_mapping(
        {"enabled": True, "provider": "fake", "account_name": "test-account"}
    )


@pytest.fixture
def fake_provider(messages: tuple[EmailMessage, ...]) -> FakeEmailProvider:
    return FakeEmailProvider(messages)


@pytest.fixture
def email_service(
    email_configuration: EmailConfiguration, fake_provider: FakeEmailProvider
) -> EmailService:
    return EmailService(email_configuration, fake_provider)
