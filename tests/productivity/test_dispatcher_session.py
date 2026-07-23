from omega.execution import ProductivityActionDispatcher
from omega.models import CommandSource, IntentType
from omega.productivity.repositories import ProductivityRepository
from omega.productivity.service import ProductivityService
from omega.safety import SafeExecutionGateway
from omega.session import OmegaSession
from omega.understanding import CommandParser


def test_dispatcher_uses_gateway_and_executes_once(
    productivity: tuple[ProductivityService, ProductivityRepository],
) -> None:
    service, repository = productivity
    gateway = SafeExecutionGateway()
    dispatcher = ProductivityActionDispatcher(service, gateway)
    parsed = CommandParser().parse("Create a note called Project Ideas")
    result = dispatcher.dispatch(parsed)
    assert result is not None
    assert result.result.success
    assert len(repository.list_notes()) == 1
    assert len(gateway.audit.records) > 0


def test_terminal_and_voice_sources_share_session_lifecycle(
    productivity: tuple[ProductivityService, ProductivityRepository],
) -> None:
    service, repository = productivity
    gateway = SafeExecutionGateway()
    session = OmegaSession(
        {"display_name": "Anshuman"},
        {
            "activation_phrase": "Hello Omega",
            "shutdown_phrase": "Shut down Omega",
            "active_session_timeout_seconds": 300,
        },
        productivity_dispatcher=ProductivityActionDispatcher(service, gateway),
        safety_gateway=gateway,
    )
    session.handle_input("Hello Omega")
    assert "Created note" in session.handle_input(
        "Create a note called Voice-safe", source=CommandSource.VOICE
    )
    assert session.history[-1].intent is IntentType.CREATE_NOTE
    assert session.history[-1].source is CommandSource.VOICE
    assert repository.list_notes()[0].title == "Voice-safe"


def test_productivity_delete_requires_revision_scoped_confirmation(
    productivity: tuple[ProductivityService, ProductivityRepository],
) -> None:
    service, repository = productivity
    gateway = SafeExecutionGateway()
    dispatcher = ProductivityActionDispatcher(service, gateway)
    created = service.create_note("Disposable")
    result = dispatcher.dispatch(CommandParser().parse("Delete the Disposable note"))
    assert result is not None
    assert not result.result.success
    assert "confirm delete Disposable" in result.user_message
    assert repository.get_note(created.note_id) is not None
