from __future__ import annotations

from datetime import UTC, datetime

import pytest

from omega.email import (
    AttachmentMetadata,
    EmailAddress,
    EmailConfiguration,
    EmailConfigurationError,
    EmailDraft,
    EmailMessage,
    EmailPage,
    EmailSearchQuery,
    EmailValidationError,
)


def test_configuration_defaults_are_disabled_and_credential_free() -> None:
    value = EmailConfiguration.from_mapping({})
    assert value.enabled is False
    assert value.provider is None
    assert not hasattr(value, "password")
    assert not hasattr(value, "token")


@pytest.mark.parametrize(
    "values",
    [
        {"enabled": True, "provider": None},
        {"provider": "gmail"},
        {"maximum_messages_per_request": 0},
        {"maximum_recipients": 51},
        {"provider_timeout_seconds": 0},
        {"allow_attachment_downloads": True},
        {"require_confirmation_for_send": False},
        {"require_confirmation_for_archive": False},
        {"password": "secret"},
    ],
)
def test_configuration_rejects_unsafe_or_unknown_values(
    values: dict[str, object],
) -> None:
    with pytest.raises(EmailConfigurationError):
        EmailConfiguration.from_mapping(values)


@pytest.mark.parametrize(
    "address",
    ["a@example.com", "First.Last+tag@Example.COM", "user@sub.example.co.uk"],
)
def test_email_address_normalizes_domain(address: str) -> None:
    assert str(EmailAddress(address)).rsplit("@", 1)[1].islower()


@pytest.mark.parametrize(
    "address",
    [
        "missing-at.example.com",
        "a@example",
        "a..b@example.com",
        "victim@example.com\nBcc: attacker@example.com",
        "a@localhost",
        "",
    ],
)
def test_email_address_rejects_malformed_and_header_injection(address: str) -> None:
    with pytest.raises(EmailValidationError):
        EmailAddress(address)


@pytest.mark.parametrize(
    "filename", ["../secret.txt", "..\\secret.txt", "/tmp/a", ".."]
)
def test_attachment_metadata_rejects_dangerous_names(filename: str) -> None:
    with pytest.raises(EmailValidationError):
        AttachmentMetadata("attachment-1", filename, "text/plain", 1)


def test_models_require_timezone_aware_timestamps() -> None:
    with pytest.raises(EmailValidationError):
        EmailMessage(
            "message-1",
            None,
            EmailAddress("a@example.com"),
            (EmailAddress("b@example.com"),),
            "subject",
            datetime.now(),
            "body",
        )


def test_draft_bounds_and_header_injection() -> None:
    now = datetime.now(UTC)
    with pytest.raises(EmailValidationError):
        EmailDraft(
            "draft-1",
            (EmailAddress("a@example.com"),),
            "Hello\nBcc: attacker@example.com",
            "body",
            now,
            now,
        )
    with pytest.raises(EmailValidationError):
        EmailDraft("draft-1", (), "subject", "body", now, now)


def test_search_requires_filter_and_valid_date_range() -> None:
    with pytest.raises(EmailValidationError):
        EmailSearchQuery()
    with pytest.raises(EmailValidationError):
        EmailSearchQuery(
            text="query",
            start_at=datetime(2026, 2, 1, tzinfo=UTC),
            end_at=datetime(2026, 1, 1, tzinfo=UTC),
        )


def test_page_enforces_bound() -> None:
    with pytest.raises(EmailValidationError):
        EmailPage((), 0)
