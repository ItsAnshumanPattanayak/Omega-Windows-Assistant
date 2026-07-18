from collections.abc import Mapping

import pytest

from omega.core.exceptions import PolicyConfigurationError
from omega.models import IntentType, PermissionDecision, RiskLevel
from omega.safety import PermissionConfiguration, PermissionPolicyEngine


@pytest.mark.parametrize(
    "intent,decision",
    [
        (IntentType.READ_FILE, PermissionDecision.ALLOW),
        (IntentType.CREATE_FILE, PermissionDecision.ALLOW),
        (IntentType.OPEN_APPLICATION, PermissionDecision.ALLOW),
        (IntentType.CLOSE_APPLICATION, PermissionDecision.REQUIRE_CONFIRMATION),
        (IntentType.MOVE_FILE, PermissionDecision.REQUIRE_CONFIRMATION),
        (IntentType.MOVE_FOLDER, PermissionDecision.REQUIRE_CONFIRMATION),
        (IntentType.DELETE_FILE, PermissionDecision.DENY),
        (IntentType.DELETE_FOLDER, PermissionDecision.DENY),
        (IntentType.UNKNOWN, PermissionDecision.DENY),
    ],
)
def test_default_permission_outcomes(context_factory, intent, decision):
    context = context_factory(intent, text=intent.value, risk=RiskLevel.LOW)
    evaluation = PermissionPolicyEngine().evaluate(
        context, confirmation_prompt="Use the exact confirmation."
    )
    assert evaluation.decision is decision


def test_denial_precedence_and_default_deny(context_factory):
    context = context_factory(
        IntentType.MOVE_FILE,
        parameters={"source_file": r"C:\Windows\notes.txt"},
        risk=RiskLevel.HIGH,
    )
    evaluation = PermissionPolicyEngine().evaluate(
        context, confirmation_prompt="confirm move"
    )
    assert evaluation.decision is PermissionDecision.DENY
    assert evaluation.denied_by is not None


def test_configuration_can_disable_safe_action(context_factory):
    config = PermissionConfiguration.from_mapping(
        {
            "default_decision": "deny",
            "actions": {"read_file": {"enabled": False}},
        }
    )
    evaluation = PermissionPolicyEngine(configuration=config).evaluate(
        context_factory(IntentType.READ_FILE)
    )
    assert evaluation.decision is PermissionDecision.DENY
    assert evaluation.reason_code == "ACTION_DISABLED"


@pytest.mark.parametrize(
    "configuration",
    [
        {"default_decision": "allow", "actions": {}},
        {
            "default_decision": "deny",
            "actions": {"delete_file": {"enabled": True}},
        },
        {
            "default_decision": "deny",
            "actions": {"not_an_intent": {"enabled": True}},
        },
        {
            "default_decision": "deny",
            "actions": {"read_file": {"enabled": True, "maximum_risk": "safe"}},
        },
    ],
)
def test_unsafe_or_malformed_configuration_fails_closed(configuration: Mapping):
    with pytest.raises(PolicyConfigurationError):
        PermissionConfiguration.from_mapping(configuration)


def test_hard_boundary_is_not_overridden_by_missing_rule(context_factory):
    config = PermissionConfiguration.from_mapping(
        {"default_decision": "deny", "actions": {}}
    )
    evaluation = PermissionPolicyEngine(configuration=config).evaluate(
        context_factory(IntentType.DELETE_FILE, risk=RiskLevel.LOW)
    )
    assert evaluation.decision is PermissionDecision.DENY
    assert "Phase 8" in evaluation.user_message
