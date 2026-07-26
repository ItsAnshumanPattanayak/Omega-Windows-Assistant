from __future__ import annotations

from datetime import UTC, datetime
from types import MethodType
from uuid import UUID, uuid4

import pytest

from omega.database import (
    ActionRepository,
    CommandRepository,
    DatabaseConfiguration,
    DatabaseConnectionFactory,
    ExecutionPersistence,
    MigrationRunner,
)
from omega.email import (
    EmailAddress,
    EmailConfiguration,
    EmailProviderError,
    EmailService,
    FakeEmailProvider,
)
from omega.execution import EmailActionDispatcher
from omega.gui.controller import GuiController
from omega.models import CommandSource, IntentType
from omega.safety import ConfirmationManager, SafeExecutionGateway
from omega.understanding.parser import CommandParser


@pytest.mark.parametrize(
    ("text", "intent"),
    [
        ("Show my latest emails", IntentType.LIST_EMAILS),
        ("Show unread emails", IntentType.LIST_UNREAD_EMAILS),
        ("Search my emails for budget", IntentType.SEARCH_EMAILS),
        ("Find emails from sender@example.com", IntentType.SEARCH_EMAILS),
        ("Open email number 2", IntentType.READ_EMAIL),
        ("Summarize this email", IntentType.SUMMARIZE_EMAIL),
        ("Draft an email to person@example.com", IntentType.CREATE_EMAIL_DRAFT),
        ("Draft a reply to this email", IntentType.CREATE_EMAIL_REPLY_DRAFT),
        ("Show my drafts", IntentType.LIST_EMAIL_DRAFTS),
        ("Send this draft", IntentType.SEND_EMAIL_DRAFT),
        ("Send draft number 2", IntentType.SEND_EMAIL_DRAFT),
        ("Archive this email", IntentType.ARCHIVE_EMAIL),
        ("Show attachments for this email", IntentType.SHOW_EMAIL_ATTACHMENTS),
    ],
)
def test_email_parser_intents(text: str, intent: IntentType) -> None:
    result = CommandParser().parse(text)
    assert result.command.intent is intent
    assert result.matched and not result.requires_clarification


def test_parser_extracts_bounded_email_entities() -> None:
    parser = CommandParser()
    result = parser.parse("Find emails from sender@example.com")
    assert result.command.entities[0].name == "email_sender"
    result = parser.parse("Draft an email to person@example.com subject Project update")
    assert [(item.name, item.value) for item in result.command.entities] == [
        ("email_recipient", "person@example.com"),
        ("email_subject", "Project update"),
    ]


def _dispatcher(
    email_service: EmailService, gateway: SafeExecutionGateway | None = None
) -> EmailActionDispatcher:
    return EmailActionDispatcher(email_service, gateway or SafeExecutionGateway())


def _dispatch(
    dispatcher: EmailActionDispatcher,
    text: str,
    session_id: UUID,
    *,
    source: CommandSource = CommandSource.TEXT,
):
    parsed = CommandParser().parse(text, session_id, source=source)
    value = dispatcher.dispatch(parsed)
    assert value is not None
    return value


def test_complete_fake_provider_flow_requires_confirmation(
    email_service: EmailService, fake_provider: FakeEmailProvider
) -> None:
    session_id = uuid4()
    gateway = SafeExecutionGateway()
    dispatcher = _dispatcher(email_service, gateway)

    listing = _dispatch(dispatcher, "Show my latest emails", session_id)
    assert listing.result.success and "Quarterly plan" in listing.user_message
    reading = _dispatch(dispatcher, "Open email number 1", session_id)
    assert reading.result.success and "Please review" in reading.user_message
    summary = _dispatch(dispatcher, "Summarize this email", session_id)
    assert summary.result.success and "local" not in summary.user_message.casefold()
    draft = _dispatch(
        dispatcher,
        "Draft an email to person@example.com subject Hello",
        session_id,
    )
    assert draft.result.success and "not been sent" in draft.user_message
    assert fake_provider.send_count == 0

    send = _dispatch(dispatcher, "Send this draft", session_id)
    assert not send.result.success
    assert "Review this draft" in send.user_message
    pending = gateway.confirmations.get(session_id)
    assert pending is not None
    wrong = gateway.handle_confirmation("confirm send draft wrong", session_id)
    assert wrong is not None and not wrong.result.success
    assert fake_provider.send_count == 0
    sent = gateway.handle_confirmation(pending.expected_confirmation, session_id)
    assert sent is not None and sent.result.success
    assert fake_provider.send_count == 1
    replay = gateway.handle_confirmation(pending.expected_confirmation, session_id)
    assert replay is not None and not replay.result.success
    assert fake_provider.send_count == 1

    _dispatch(dispatcher, "Show my latest emails", session_id)
    _dispatch(dispatcher, "Open email number 1", session_id)
    archive = _dispatch(dispatcher, "Archive this email", session_id)
    assert not archive.result.success
    pending_archive = gateway.confirmations.get(session_id)
    assert pending_archive is not None
    archived = gateway.handle_confirmation(
        pending_archive.expected_confirmation, session_id
    )
    assert archived is not None and archived.result.success
    assert fake_provider.archive_count == 1


def test_stale_confirmation_and_voice_low_confidence_do_not_send(
    email_service: EmailService, fake_provider: FakeEmailProvider
) -> None:
    clock = [0.0]
    manager = ConfirmationManager(
        timeout_seconds=5,
        monotonic_clock=lambda: clock[0],
        now_provider=lambda: datetime(2026, 1, 1, tzinfo=UTC),
    )
    gateway = SafeExecutionGateway(confirmations=manager)
    dispatcher = _dispatcher(email_service, gateway)
    session_id = uuid4()
    email_service.create_draft(session_id, (EmailAddress("person@example.com"),))
    proposal = _dispatch(
        dispatcher,
        "Send this draft",
        session_id,
        source=CommandSource.VOICE,
    )
    assert not proposal.result.success and fake_provider.send_count == 0
    pending = manager.get(session_id)
    assert pending is not None
    clock[0] = 5.1
    expired = gateway.handle_confirmation(pending.expected_confirmation, session_id)
    assert expired is not None and not expired.result.success
    assert fake_provider.send_count == 0


def test_persistent_history_uses_redacted_email_command(
    tmp_path, email_service: EmailService
) -> None:
    factory = DatabaseConnectionFactory(
        DatabaseConfiguration(), database_path=tmp_path / "omega.db"
    )
    MigrationRunner(factory).migrate()
    commands = CommandRepository(factory)
    gateway = SafeExecutionGateway(
        persistence=ExecutionPersistence(commands, ActionRepository(factory))
    )
    dispatcher = _dispatcher(email_service, gateway)
    session_id = uuid4()
    parsed = CommandParser().parse(
        "Draft an email to private@example.com subject Confidential",
        session_id,
    )
    result = dispatcher.dispatch(parsed)
    assert result is not None and result.result.success
    stored = commands.get(parsed.command.command_id)
    assert stored is not None
    assert stored.original_text == "[email command: create_email_draft]"
    assert "private@example.com" not in stored.original_text
    assert stored.metadata["privacy_redacted"] is True


def test_gui_email_helpers_use_normal_command_lifecycle() -> None:
    controller = object.__new__(GuiController)
    submitted: list[str] = []

    def submit(self, text: str) -> bool:
        submitted.append(text)
        return True

    controller.submit_command = MethodType(submit, controller)
    assert controller.list_emails()
    assert controller.search_emails("budget")
    assert controller.create_email_draft("person@example.com", "Hello")
    assert controller.send_email_draft()
    assert submitted == [
        "show my latest emails",
        "search my emails for budget",
        "draft an email to person@example.com subject Hello",
        "send this draft",
    ]


def test_no_permanent_delete_or_attachment_download_provider_surface() -> None:
    names = set(dir(FakeEmailProvider))
    assert "delete_message" not in names
    assert "download_attachment" not in names


def test_provider_error_credentials_are_redacted() -> None:
    class FailingProvider(FakeEmailProvider):
        def list_messages(self, *, limit: int, unread_only: bool = False):
            raise EmailProviderError("password=hunter2 token=secret")

    service = EmailService(
        EmailConfiguration(enabled=True, provider="fake"), FailingProvider()
    )
    result = _dispatch(_dispatcher(service), "Show my latest emails", uuid4())
    assert not result.result.success
    assert "hunter2" not in result.user_message
    assert "secret" not in result.result.message
    assert result.result.error is not None
    assert "hunter2" not in str(result.result.error.to_dict())
