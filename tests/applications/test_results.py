import pytest

from omega.applications import (
    ApplicationDiscoveryResult,
    ApplicationLaunchTarget,
    ApplicationProcess,
    LaunchTargetKind,
    ProcessOperationResult,
)
from omega.core.exceptions import ModelValidationError


def test_launch_target_process_and_operation_serialization() -> None:
    target = ApplicationLaunchTarget(
        "sample", LaunchTargetKind.EXECUTABLE, r"C:\Apps\sample.exe"
    )
    process = ApplicationProcess(10, "sample.exe", "sample", created_at=1.0)
    operation = ProcessOperationResult(attempted=1, stopped=1)

    assert target.to_dict()["kind"] == "executable"
    assert process.to_dict()["pid"] == 10
    assert operation.complete is True


def test_result_models_reject_invalid_states() -> None:
    with pytest.raises(ModelValidationError):
        ApplicationDiscoveryResult(True, "sample")
    with pytest.raises(ModelValidationError):
        ApplicationProcess(0, "sample.exe", "sample")
    with pytest.raises(ModelValidationError):
        ProcessOperationResult(attempted=-1)
