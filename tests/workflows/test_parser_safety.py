from uuid import uuid4

import pytest

from omega.models import Action, IntentType, RiskLevel, UserCommand
from omega.safety import RiskClassifier, SafetyContext
from omega.understanding import CommandParser


@pytest.mark.parametrize(
    ("text", "intent"),
    [
        ("create workflow named Morning Setup", IntentType.CREATE_WORKFLOW),
        ("add step: display message Hello", IntentType.ADD_WORKFLOW_STEP),
        ("remove step 3", IntentType.REMOVE_WORKFLOW_STEP),
        ("move step 4 before step 2", IntentType.MOVE_WORKFLOW_STEP),
        ("list my workflows", IntentType.LIST_WORKFLOWS),
        ("show workflow Morning Setup", IntentType.SHOW_WORKFLOW),
        ("preview workflow Morning Setup", IntentType.PREVIEW_WORKFLOW),
        ("validate workflow Morning Setup", IntentType.VALIDATE_WORKFLOW),
        ("run Morning Setup", IntentType.RUN_WORKFLOW),
        ("pause this workflow", IntentType.PAUSE_WORKFLOW),
        ("resume this workflow", IntentType.RESUME_WORKFLOW),
        ("cancel this workflow", IntentType.CANCEL_WORKFLOW),
        ("delete workflow Morning Setup", IntentType.DELETE_WORKFLOW),
        ("show workflow history", IntentType.SHOW_WORKFLOW_HISTORY),
        ("export workflow Morning Setup", IntentType.EXPORT_WORKFLOW),
        ("import workflow from workflow.json", IntentType.IMPORT_WORKFLOW),
    ],
)
def test_workflow_intents(text: str, intent: IntentType) -> None:
    result = CommandParser().parse(text)
    assert result.matched and result.command.intent is intent


def test_workflow_reference_extraction() -> None:
    result = CommandParser().parse("run Morning Setup")
    assert result.command.entities[0].value == "Morning Setup"


def test_delete_is_high_risk() -> None:
    command = UserCommand("delete workflow test", intent=IntentType.DELETE_WORKFLOW)
    action = Action(command.command_id, command.intent, risk_level=RiskLevel.LOW)
    context = SafetyContext(command, action, uuid4())
    assert RiskClassifier().classify(context) is RiskLevel.HIGH


def test_shell_and_code_are_not_intents() -> None:
    for text in (
        "run shell dir",
        "execute python print secret",
        "call webhook example.com",
    ):
        result = CommandParser().parse(text)
        assert result.command.intent is not IntentType.RUN_WORKFLOW
        assert result.requires_clarification or not result.matched
