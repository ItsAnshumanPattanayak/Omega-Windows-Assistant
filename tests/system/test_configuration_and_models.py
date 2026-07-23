from __future__ import annotations

import pytest

from omega.core.exceptions import ConfigurationError, ModelValidationError
from omega.system import (
    AudioState,
    BatterySummary,
    BrightnessState,
    CpuSummary,
    MemorySummary,
    PowerActionRequest,
    PowerOperation,
    ProcessSummary,
    SystemConfiguration,
)


def test_configuration_safe_defaults_and_strict_validation() -> None:
    value = SystemConfiguration.from_mapping({})
    assert value.process_termination_enabled is False
    assert value.minimum_brightness_percent == 10

    with pytest.raises(ConfigurationError):
        SystemConfiguration.from_mapping({"unknown": True})
    with pytest.raises(ConfigurationError):
        SystemConfiguration.from_mapping({"process_termination_enabled": True})
    with pytest.raises(ConfigurationError):
        SystemConfiguration.from_mapping({"maximum_process_results": True})
    with pytest.raises(ConfigurationError):
        SystemConfiguration.from_mapping({"minimum_brightness_percent": 0})


def test_models_validate_bounds_and_serialize() -> None:
    cpu = CpuSummary(8, 4, 12.5)
    memory = MemorySummary(100, 40, 60, 60.0)
    assert cpu.to_dict()["logical_processors"] == 8
    assert memory.to_dict()["available_bytes"] == 40
    assert BatterySummary(False).to_dict()["available"] is False
    assert AudioState(50, False).to_dict() == {
        "volume_percent": 50,
        "muted": False,
    }
    assert BrightnessState((25, 50)).to_dict()["percentages"] == [25, 50]
    assert ProcessSummary(1, "safe.exe", 0.0, 1.0, "running").to_dict()["pid"] == 1
    assert PowerActionRequest(PowerOperation.RESTART, 10).countdown_seconds == 10

    with pytest.raises(ModelValidationError):
        CpuSummary(0, None, 0)
    with pytest.raises(ModelValidationError):
        AudioState(101, False)
    with pytest.raises(ModelValidationError):
        BrightnessState(())
    with pytest.raises(ModelValidationError):
        BatterySummary(False, 50, False)
