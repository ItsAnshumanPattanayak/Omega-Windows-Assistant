"""Deterministic zero-side-effect workflow handler registry."""

from collections.abc import Callable, Mapping

from omega.models._serialization import JsonValue
from omega.workflows.models import WorkflowStep, WorkflowStepType


class FakeWorkflowHandlers:
    def __init__(self) -> None:
        self.calls: list[str] = []
        self.shell_calls = self.network_calls = self.desktop_calls = 0

    def handle(self, step: WorkflowStep, context: Mapping[str, JsonValue]) -> JsonValue:
        del context
        self.calls.append(step.step_id)
        if step.arguments.get("fail") is True:
            raise RuntimeError("fake failure")
        return step.arguments.get("result", {"step_type": step.step_type.value})

    def registry(
        self,
    ) -> dict[
        WorkflowStepType,
        Callable[[WorkflowStep, Mapping[str, JsonValue]], JsonValue],
    ]:
        return {kind: self.handle for kind in WorkflowStepType}
