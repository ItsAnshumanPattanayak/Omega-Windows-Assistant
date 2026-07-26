"""Deterministic low-risk fake plugin used by tests and examples."""

from collections.abc import Mapping

from omega.models._serialization import JsonValue
from omega.plugins.models import PluginContext


class FakeReadOnlyPlugin:
    def __init__(self, context: PluginContext) -> None:
        self.context = context
        self.calls: list[str] = []
        self.stopped = False

    def read(self, argument: str) -> JsonValue:
        self.calls.append(argument)
        return {"message": f"Omega plugin received {argument}"}

    def display_step(self, arguments: Mapping[str, JsonValue]) -> JsonValue:
        return {"display": arguments.get("message", "")}

    def shutdown(self) -> None:
        self.stopped = True
