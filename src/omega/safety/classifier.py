"""Deterministic and conservative risk classification."""

from __future__ import annotations

from omega.models import IntentType, RiskLevel
from omega.safety.models import SafetyContext

_ORDER = {
    RiskLevel.LOW: 0,
    RiskLevel.MEDIUM: 1,
    RiskLevel.HIGH: 2,
    RiskLevel.CRITICAL: 3,
}

_LOW = frozenset(
    {
        IntentType.CHECK_APPLICATION_STATUS,
        IntentType.READ_FILE,
        IntentType.OPEN_FILE,
        IntentType.SEARCH_FILE,
        IntentType.CHECK_FILE_EXISTENCE,
        IntentType.GET_FILE_INFORMATION,
        IntentType.OPEN_FOLDER,
        IntentType.LIST_FOLDER,
        IntentType.SEARCH_FOLDER,
        IntentType.CHECK_FOLDER_EXISTENCE,
        IntentType.GET_FOLDER_INFORMATION,
    }
)
_MEDIUM = frozenset(
    {
        IntentType.OPEN_APPLICATION,
        IntentType.CREATE_FILE,
        IntentType.APPEND_FILE,
        IntentType.RENAME_FILE,
        IntentType.COPY_FILE,
        IntentType.CREATE_FOLDER,
        IntentType.RENAME_FOLDER,
        IntentType.COPY_FOLDER,
    }
)
_HIGH = frozenset(
    {
        IntentType.CLOSE_APPLICATION,
        IntentType.WRITE_FILE,
        IntentType.MOVE_FILE,
        IntentType.MOVE_FOLDER,
    }
)
_CRITICAL = frozenset({IntentType.DELETE_FILE, IntentType.DELETE_FOLDER})


class RiskClassifier:
    """Classify using only typed intent and validated target state."""

    def classify(self, context: SafetyContext) -> RiskLevel:
        intent = context.action.intent
        if context.additional_context.get("protected_resource") is True:
            computed = RiskLevel.CRITICAL
        elif context.additional_context.get("shell_like") is True:
            computed = RiskLevel.CRITICAL
        elif context.additional_context.get("destination_conflict") is True:
            computed = RiskLevel.HIGH
        elif intent in _LOW:
            computed = RiskLevel.LOW
        elif intent in _MEDIUM:
            computed = RiskLevel.MEDIUM
        elif intent is IntentType.WRITE_FILE and not context.additional_context.get(
            "target_has_content", context.target_exists
        ):
            computed = RiskLevel.MEDIUM
        elif intent in _HIGH:
            computed = RiskLevel.HIGH
        elif intent in _CRITICAL or intent is IntentType.UNKNOWN:
            computed = RiskLevel.CRITICAL
        else:
            computed = RiskLevel.CRITICAL
        provisional = context.action.risk_level
        return provisional if _ORDER[provisional] > _ORDER[computed] else computed
