from collections.abc import Mapping

import pytest

from omega.core.exceptions import PolicyConfigurationError
from omega.models import (
    IntentType,
    PermissionDecision,
    RiskLevel,
)
from omega.safety import (
    PermissionConfiguration,
    PermissionPolicyEngine,
)


@pytest.mark.parametrize(
    "intent,decision",
    [
        (
            IntentType.READ_FILE,
            PermissionDecision.ALLOW,
        ),
        (
            IntentType.CREATE_FILE,
            PermissionDecision.ALLOW,
        ),
        (
            IntentType.OPEN_APPLICATION,
            PermissionDecision.ALLOW,
        ),
        (
            IntentType.CLOSE_APPLICATION,
            PermissionDecision.REQUIRE_CONFIRMATION,
        ),
        (
            IntentType.MOVE_FILE,
            PermissionDecision.REQUIRE_CONFIRMATION,
        ),
        (
            IntentType.MOVE_FOLDER,
            PermissionDecision.REQUIRE_CONFIRMATION,
        ),
        (
            IntentType.DELETE_FILE,
            PermissionDecision.REQUIRE_CONFIRMATION,
        ),
        (
            IntentType.DELETE_FOLDER,
            PermissionDecision.REQUIRE_CONFIRMATION,
        ),
        (
            IntentType.UNKNOWN,
            PermissionDecision.DENY,
        ),
    ],
)
def test_default_permission_outcomes(
    context_factory,
    intent: IntentType,
    decision: PermissionDecision,
) -> None:
    context = context_factory(
        intent,
        text=intent.value,
        risk=RiskLevel.LOW,
    )

    evaluation = PermissionPolicyEngine().evaluate(
        context,
        confirmation_prompt=("Use the exact confirmation."),
    )

    assert evaluation.decision is decision

    if intent in {
        IntentType.DELETE_FILE,
        IntentType.DELETE_FOLDER,
    }:
        assert evaluation.risk_level is RiskLevel.CRITICAL
        assert evaluation.requires_confirmation


def test_denial_precedence_and_default_deny(
    context_factory,
) -> None:
    context = context_factory(
        IntentType.MOVE_FILE,
        parameters={"source_file": r"C:\Windows\notes.txt"},
        risk=RiskLevel.HIGH,
    )

    evaluation = PermissionPolicyEngine().evaluate(
        context,
        confirmation_prompt="confirm move",
    )

    assert evaluation.decision is PermissionDecision.DENY
    assert evaluation.denied_by is not None


def test_configuration_can_disable_safe_action(
    context_factory,
) -> None:
    configuration = PermissionConfiguration.from_mapping(
        {
            "default_decision": "deny",
            "actions": {"read_file": {"enabled": False}},
        }
    )

    evaluation = PermissionPolicyEngine(configuration=configuration).evaluate(
        context_factory(IntentType.READ_FILE)
    )

    assert evaluation.decision is PermissionDecision.DENY
    assert evaluation.reason_code == "ACTION_DISABLED"


@pytest.mark.parametrize(
    "configuration",
    [
        {
            "default_decision": "allow",
            "actions": {},
        },
        {
            "default_decision": "deny",
            "actions": {"delete_file": {"enabled": True}},
        },
        {
            "default_decision": "deny",
            "actions": {
                "delete_file": {
                    "enabled": True,
                    "maximum_risk": "critical",
                    "requires_confirmation": False,
                }
            },
        },
        {
            "default_decision": "deny",
            "actions": {
                "delete_file": {
                    "enabled": True,
                    "maximum_risk": "high",
                    "requires_confirmation": True,
                }
            },
        },
        {
            "default_decision": "deny",
            "actions": {"not_an_intent": {"enabled": True}},
        },
        {
            "default_decision": "deny",
            "actions": {
                "read_file": {
                    "enabled": True,
                    "maximum_risk": "safe",
                }
            },
        },
    ],
)
def test_unsafe_or_malformed_configuration_fails_closed(
    configuration: Mapping,
) -> None:
    with pytest.raises(PolicyConfigurationError):
        PermissionConfiguration.from_mapping(configuration)


def test_missing_delete_rule_remains_denied(
    context_factory,
) -> None:
    configuration = PermissionConfiguration.from_mapping(
        {
            "default_decision": "deny",
            "actions": {},
        }
    )

    evaluation = PermissionPolicyEngine(configuration=configuration).evaluate(
        context_factory(
            IntentType.DELETE_FILE,
            risk=RiskLevel.LOW,
        )
    )

    assert evaluation.decision is PermissionDecision.DENY
    assert evaluation.reason_code == "ACTION_DISABLED"
    assert not evaluation.requires_confirmation
