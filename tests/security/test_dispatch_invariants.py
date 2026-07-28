import pytest

from omega.core.exceptions import SecurityValidationError
from omega.models import Action, IntentType, UserCommand
from omega.safety.models import SafetyContext
from omega.security.invariants import require_dispatchable


def _context(
    intent: IntentType, *, command_metadata: dict[str, bool] | None = None
) -> SafetyContext:
    command = UserCommand(
        "safe test command", intent=intent, metadata=command_metadata or {}
    )
    return SafetyContext(command, Action(command.command_id, intent))


def test_unknown_intent_cannot_reach_policy_or_executor() -> None:
    with pytest.raises(SecurityValidationError, match="Unknown intents"):
        require_dispatchable(_context(IntentType.UNKNOWN))


def test_model_output_cannot_authorize_an_action() -> None:
    with pytest.raises(SecurityValidationError, match="Model output"):
        require_dispatchable(
            _context(IntentType.HELP, command_metadata={"model_authorized": True})
        )


@pytest.mark.parametrize("key", ["safety_bypass", "shell_like"])
def test_bypass_and_shell_context_fail_closed(key: str) -> None:
    context = _context(IntentType.HELP)
    context = SafetyContext(
        context.command, context.action, additional_context={key: True}
    )
    with pytest.raises(SecurityValidationError):
        require_dispatchable(context)


def test_typed_known_action_passes_universal_invariants() -> None:
    require_dispatchable(_context(IntentType.HELP))
