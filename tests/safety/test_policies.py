from omega.models import IntentType, PermissionDecision, RiskLevel
from omega.safety import PermissionPolicyEngine


def test_explicit_policy_order_and_ids_are_stable():
    engine = PermissionPolicyEngine()
    priorities = [policy.priority for policy in engine.policies]
    ids = [policy.policy_id for policy in engine.policies]
    assert priorities == sorted(priorities)
    assert len(ids) == len(set(ids))
    assert "SAFETY-SHELL-DENY-001" in ids
    assert "SAFETY-PROTECTED-PATH-001" in ids
    assert "SAFETY-APP-CLOSE-001" in ids


def test_confirmation_precedes_allow(context_factory):
    context = context_factory(IntentType.MOVE_FILE, risk=RiskLevel.HIGH)
    result = PermissionPolicyEngine().evaluate(
        context, confirmation_prompt="confirm move notes.txt"
    )
    assert result.decision is PermissionDecision.REQUIRE_CONFIRMATION
    assert result.requires_confirmation


def test_shell_and_unsafe_extension_have_specific_denials(context_factory):
    shell = PermissionPolicyEngine().evaluate(
        context_factory(IntentType.UNKNOWN, text="Run echo hello")
    )
    script = PermissionPolicyEngine().evaluate(
        context_factory(
            IntentType.CREATE_FILE,
            text="Create virus.ps1 on Desktop",
            parameters={"file_name": "virus.ps1"},
            risk=RiskLevel.MEDIUM,
        )
    )
    assert shell.reason_code == "ARBITRARY_SHELL_DENIED"
    assert script.reason_code == "UNSAFE_EXTENSION_DENIED"
