from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest

from omega.app import OmegaApplication
from omega.execution import PreferenceDispatcher
from omega.models import (
    Action,
    ConfirmationStatus,
    IntentType,
    PermissionDecision,
    RiskLevel,
    UserCommand,
)
from omega.personalization import (
    FakePreferenceRepository,
    PersonalizationConfiguration,
    PreferenceResolver,
    PreferenceService,
    PreferenceValidator,
    ProfileExportService,
    ProfileImportService,
)
from omega.safety import RiskClassifier, SafeExecutionGateway, SafetyContext
from omega.understanding import CommandParser


def _dispatcher() -> tuple[PreferenceDispatcher, PreferenceService]:
    configuration = PersonalizationConfiguration()
    repository = FakePreferenceRepository()
    service = PreferenceService(
        configuration,
        repository,
        PreferenceValidator(configuration, application_aliases=("chrome",)),
        PreferenceResolver(repository),
    )
    return (
        PreferenceDispatcher(
            service,
            ProfileExportService(service, configuration),
            ProfileImportService(service, configuration),
            SafeExecutionGateway(),
        ),
        service,
    )


def test_dispatcher_sets_preference_through_gateway() -> None:
    dispatcher, service = _dispatcher()
    parsed = CommandParser().parse("Keep responses concise", uuid4())
    result = dispatcher.dispatch(parsed)
    assert result is not None
    assert result.result.success
    assert result.action.intent is IntentType.SET_PREFERENCE
    assert result.action.metadata["preference_values_omitted"] is True
    assert service.resolver.resolve("response_verbosity").value == "concise"


def test_broad_reset_is_awaiting_scoped_confirmation() -> None:
    dispatcher, service = _dispatcher()
    service.set_preference("response_verbosity", "concise")
    result = dispatcher.dispatch(
        CommandParser().parse("Reset all preferences", uuid4())
    )
    assert result is not None
    assert result.action.requires_confirmation
    assert not result.result.success
    assert service.list_preferences()


@pytest.mark.parametrize(
    ("intent", "risk"),
    [
        (IntentType.SHOW_PREFERENCES, RiskLevel.LOW),
        (IntentType.SET_PREFERENCE, RiskLevel.LOW),
        (IntentType.RESET_ALL_PREFERENCES, RiskLevel.MEDIUM),
        (IntentType.IMPORT_PROFILE, RiskLevel.MEDIUM),
        (IntentType.DELETE_PROFILE, RiskLevel.MEDIUM),
    ],
)
def test_personalization_risk_classification(intent, risk) -> None:
    command = UserCommand(intent.value, intent=intent)
    action = Action(
        command.command_id,
        intent,
        risk_level=RiskLevel.LOW,
        permission_decision=PermissionDecision.ALLOW,
        confirmation_status=ConfirmationStatus.NOT_REQUIRED,
        requires_confirmation=False,
    )
    context = SafetyContext(command, action, uuid4())
    assert RiskClassifier().classify(context) is risk


def test_application_composes_personalization_without_side_effects(
    tmp_path: Path,
) -> None:
    application = OmegaApplication(database_path=tmp_path / "omega.db")
    try:
        application.session.handle_input("Hello Omega")
        response = application.session.handle_input("Show my profile")
        assert "Active profile: Default" in response
        assert application.preference_repository.active_profile_id() is not None
    finally:
        application.shutdown()
