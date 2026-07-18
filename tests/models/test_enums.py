"""Tests for stable serialized model enums."""

import pytest

from omega.models import ActionStatus, EntityType, IntentType, RiskLevel


def test_enum_values_round_trip_and_are_unique() -> None:
    assert IntentType.OPEN_APPLICATION.value == "open_application"
    assert IntentType("open_application") is IntentType.OPEN_APPLICATION
    assert RiskLevel("critical") is RiskLevel.CRITICAL
    assert EntityType("application") is EntityType.APPLICATION
    assert len({item.value for item in ActionStatus}) == len(ActionStatus)


def test_invalid_enum_value_is_rejected() -> None:
    with pytest.raises(ValueError):
        IntentType("launch_everything")
