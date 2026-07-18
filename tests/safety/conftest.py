from collections.abc import Callable
from uuid import UUID, uuid4

import pytest

from omega.models import (
    Action,
    ConfirmationStatus,
    IntentType,
    PermissionDecision,
    RiskLevel,
    UserCommand,
)
from omega.safety import SafetyContext


@pytest.fixture
def context_factory() -> Callable[..., SafetyContext]:
    def build(
        intent: IntentType = IntentType.READ_FILE,
        *,
        text: str = "Read notes.txt from Desktop",
        parameters: dict | None = None,
        risk: RiskLevel = RiskLevel.LOW,
        session_id: UUID | None = None,
        **context_values,
    ) -> SafetyContext:
        command = UserCommand(text, intent=intent, session_id=session_id)
        action = Action(
            command.command_id,
            intent,
            parameters=parameters or {},
            risk_level=risk,
            permission_decision=PermissionDecision.ALLOW,
            confirmation_status=ConfirmationStatus.NOT_REQUIRED,
            requires_confirmation=False,
        )
        return SafetyContext(
            command,
            action,
            session_id=session_id or uuid4(),
            **context_values,
        )

    return build
