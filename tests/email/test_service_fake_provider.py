from __future__ import annotations

from uuid import uuid4

import pytest

from omega.email import (
    DuplicateEmailOperationError,
    EmailAddress,
    EmailConfiguration,
    EmailNotFoundError,
    EmailProviderTimeout,
    EmailSearchQuery,
    EmailService,
    EmailUnavailableError,
    EmailValidationError,
    FakeEmailProvider,
)


def test_disabled_and_unconfigured_behavior_is_clear() -> None:
    disabled = EmailService(EmailConfiguration())
    assert disabled.status() == "Email assistance is disabled."
    with pytest.raises(EmailUnavailableError):
        disabled.list_messages(uuid4())
    unconfigured = EmailService(EmailConfiguration(enabled=True, provider="fake"))
    assert "no provider" in unconfigured.status().casefold()


def test_listing_unread_search_and_bounds(email_service: EmailService) -> None:
    session = uuid4()
    latest = email_service.list_messages(session)
    assert [item.message_id for item in latest.items] == ["message-2", "message-1"]
    unread = email_service.list_messages(session, unread_only=True)
    assert [item.message_id for item in unread.items] == ["message-2"]
    sender = email_service.search(
        session, EmailSearchQuery(sender=EmailAddress("manager@example.com"))
    )
    assert [item.subject for item in sender.items] == ["Quarterly plan"]
    subject = email_service.search(session, EmailSearchQuery(subject="lunch"))
    assert [item.message_id for item in subject.items] == ["message-1"]


def test_read_selection_is_stable_and_invalidated_by_new_results(
    email_service: EmailService,
) -> None:
    session = uuid4()
    email_service.list_messages(session)
    assert email_service.read_message(session, 1).message_id == "message-2"
    email_service.search(session, EmailSearchQuery(text="lunch"))
    with pytest.raises(EmailNotFoundError):
        email_service.read_message(session)
    assert email_service.read_message(session, 1).message_id == "message-1"


def test_invalid_selection_and_independent_sessions(
    email_service: EmailService,
) -> None:
    first, second = uuid4(), uuid4()
    email_service.list_messages(first)
    with pytest.raises(EmailNotFoundError):
        email_service.read_message(second, 1)
    with pytest.raises(EmailNotFoundError):
        email_service.read_message(first, 99)


def test_deterministic_summary_uses_source_sentences_only(
    email_service: EmailService,
) -> None:
    session = uuid4()
    email_service.list_messages(session)
    email_service.read_message(session, 1)
    summary = email_service.summarize(session)
    assert "Quarterly plan" in summary
    assert "Please review it by Friday." in summary
    assert "AI" not in summary


def test_attachment_metadata_never_downloads(
    email_service: EmailService, fake_provider: FakeEmailProvider
) -> None:
    session = uuid4()
    email_service.list_messages(session)
    email_service.read_message(session, 1)
    attachments = email_service.attachment_metadata(session)
    assert attachments[0].filename == "plan.pdf"
    assert fake_provider.network_operations == 0


def test_html_is_only_a_flag_and_plain_text_is_inert(
    email_service: EmailService,
) -> None:
    session = uuid4()
    email_service.list_messages(session)
    message = email_service.read_message(session, 1)
    assert message.html_available is True
    assert "<script" not in message.plain_text_body


def test_draft_create_update_reply_and_list(email_service: EmailService) -> None:
    session = uuid4()
    draft = email_service.create_draft(
        session, (EmailAddress("person@example.com"),), "Hello", ""
    )
    assert draft.body == ""
    assert (
        email_service.update_draft(session, body="Reviewable body").body
        == "Reviewable body"
    )
    assert email_service.list_drafts(session)[0].draft_id == draft.draft_id
    email_service.list_messages(session)
    email_service.read_message(session, 1)
    reply = email_service.create_reply_draft(session)
    assert reply.reply_to_message_id == "message-2"
    assert reply.subject == "Re: Quarterly plan"


def test_recipient_subject_and_body_limits(fake_provider: FakeEmailProvider) -> None:
    config = EmailConfiguration(
        enabled=True,
        provider="fake",
        maximum_recipients=1,
        maximum_subject_characters=5,
        maximum_draft_body_characters=5,
    )
    service = EmailService(config, fake_provider)
    session = uuid4()
    with pytest.raises(EmailValidationError):
        service.create_draft(
            session, (EmailAddress("a@example.com"), EmailAddress("b@example.com"))
        )
    with pytest.raises(EmailValidationError):
        service.create_draft(session, (EmailAddress("a@example.com"),), "longer")
    with pytest.raises(EmailValidationError):
        service.create_draft(session, (EmailAddress("a@example.com"),), body="longer")


def test_send_idempotency_and_timeout_ambiguity(
    email_service: EmailService, fake_provider: FakeEmailProvider
) -> None:
    session = uuid4()
    email_service.create_draft(
        session, (EmailAddress("a@example.com"),), "subject", "body"
    )
    outcome = email_service.send_selected_draft(session, "operation-1")
    assert outcome.status.value == "succeeded"
    assert fake_provider.send_count == 1
    with pytest.raises(DuplicateEmailOperationError):
        email_service.send_selected_draft(session, "operation-2")

    another = uuid4()
    email_service.create_draft(
        another, (EmailAddress("b@example.com"),), "subject", "body"
    )
    fake_provider.timeout_next_send = True
    with pytest.raises(EmailProviderTimeout):
        email_service.send_selected_draft(another, "operation-timeout")
    with pytest.raises(DuplicateEmailOperationError):
        email_service.send_selected_draft(another, "operation-retry")


def test_archive_is_not_delete(
    email_service: EmailService, fake_provider: FakeEmailProvider
) -> None:
    session = uuid4()
    email_service.list_messages(session)
    email_service.read_message(session, 1)
    result = email_service.archive_selected_message(session, "archive-operation")
    assert result.status.value == "succeeded"
    assert fake_provider.archive_count == 1
    assert not hasattr(fake_provider, "delete_message")
