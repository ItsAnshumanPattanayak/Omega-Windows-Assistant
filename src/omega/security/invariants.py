"""Central assertions that complement—not replace—the safety policy engine."""

from __future__ import annotations

from enum import StrEnum

from omega.core.exceptions import SecurityValidationError
from omega.models import IntentType
from omega.safety.models import SafetyContext


class SecurityInvariant(StrEnum):
    NO_UNKNOWN_INTENT_EXECUTION = "no_unknown_intent_execution"
    NO_MODEL_AUTHORIZATION = "no_model_authorization"
    NO_SAFETY_BYPASS = "no_safety_bypass"
    NO_SHELL_FROM_INPUT = "no_shell_from_input"
    EXACT_ACTION_BINDING = "exact_action_binding"


def require_dispatchable(context: SafetyContext) -> None:
    """Fail closed before policy evaluation for universally prohibited proposals."""

    additional = context.additional_context
    if (
        context.command.intent is IntentType.UNKNOWN
        and additional.get("unrecognized_guard") is not True
    ):
        raise SecurityValidationError("Unknown intents cannot execute.")
    if context.command.command_id != context.action.command_id:
        raise SecurityValidationError("Action is not bound to its exact command.")
    metadata = context.command.metadata
    if (
        metadata.get("model_authorized") is True
        or additional.get("model_authorized") is True
    ):
        raise SecurityValidationError("Model output cannot authorize an action.")
    if additional.get("safety_bypass") is True:
        raise SecurityValidationError("Safety-gateway bypass is prohibited.")
    if (
        additional.get("shell_like") is True
        and additional.get("unrecognized_guard") is not True
    ):
        raise SecurityValidationError("User-derived shell execution is prohibited.")
