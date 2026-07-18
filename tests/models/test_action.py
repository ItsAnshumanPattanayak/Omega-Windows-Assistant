"""Tests for non-executing action proposals."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from omega.core.exceptions import ModelValidationError
from omega.models import (
    Action,
    ActionStatus,
    ConfirmationStatus,
    IntentType,
    PermissionDecision,
)


def test_action_default_state_and_round_trip() -> None:
    action = Action(command_id=uuid4(), intent=IntentType.OPEN_APPLICATION)
    assert action.status is ActionStatus.PENDING
    assert action.action_id
    assert Action.from_dict(action.to_dict()).to_dict() == action.to_dict()


def test_action_parameters_and_defaults_are_independent() -> None:
    first = Action(command_id=uuid4(), intent=IntentType.CREATE_FOLDER)
    second = Action(command_id=uuid4(), intent=IntentType.CREATE_FOLDER)
    first.parameters["folder_name"] = "Projects"
    first.metadata["test"] = True
    assert second.parameters == {}
    assert second.metadata == {}
    assert first.to_dict()["parameters"] == {"folder_name": "Projects"}


def test_action_rejects_invalid_dependencies_and_confirmation_states() -> None:
    action_id = uuid4()
    with pytest.raises(ModelValidationError, match="itself"):
        Action(
            command_id=uuid4(),
            intent=IntentType.HELP,
            action_id=action_id,
            dependencies=[action_id],
        )
    dependency = uuid4()
    with pytest.raises(ModelValidationError, match="duplicate"):
        Action(
            command_id=uuid4(),
            intent=IntentType.HELP,
            dependencies=[dependency, dependency],
        )
    with pytest.raises(ModelValidationError):
        Action(
            command_id=uuid4(),
            intent=IntentType.HELP,
            requires_confirmation=False,
            confirmation_status=ConfirmationStatus.PENDING,
            permission_decision=PermissionDecision.ALLOW,
        )


def test_action_validates_lifecycle_timestamps() -> None:
    now = datetime.now(UTC)
    with pytest.raises(ModelValidationError, match="RUNNING"):
        Action(command_id=uuid4(), intent=IntentType.HELP, status=ActionStatus.RUNNING)
    with pytest.raises(ModelValidationError, match="precede"):
        Action(
            command_id=uuid4(),
            intent=IntentType.HELP,
            status=ActionStatus.SUCCEEDED,
            started_at=now,
            completed_at=now - timedelta(seconds=1),
        )
