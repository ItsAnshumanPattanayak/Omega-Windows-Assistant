import json
from dataclasses import replace

from omega.plugins import PluginConfiguration, PluginValidator
from omega.understanding import CommandParser
from omega.workflows import (
    WorkflowConfiguration,
    WorkflowDefinition,
    WorkflowPlanner,
    WorkflowStep,
    WorkflowStepType,
    WorkflowValidator,
)


def test_parser_reuses_hash_keyed_intent_results_with_a_bound() -> None:
    parser = CommandParser(intent_cache_size=2)
    for command in ("Open Chrome", "Show history", "List unread emails"):
        parser.parse(command)
    assert parser.detector.cache_size == 2
    assert (
        parser.parse("List unread emails").command.intent.value == "list_unread_emails"
    )


def test_workflow_plan_cache_is_content_bound_and_invalidates() -> None:
    workflow = WorkflowDefinition(
        "Measured",
        (WorkflowStep("message", WorkflowStepType.DISPLAY_MESSAGE),),
    )
    planner = WorkflowPlanner(WorkflowValidator(WorkflowConfiguration()), cache_size=2)
    first = planner.plan(workflow)
    second = planner.plan(workflow)
    assert first is second
    changed = replace(workflow, description="changed without authorization")
    assert planner.plan(changed) is not first
    assert planner.cache_size == 2
    planner.clear_cache()
    assert planner.cache_size == 0


def test_plugin_manifest_cache_uses_payload_fingerprint() -> None:
    raw: dict[str, object] = {
        "schema_version": 1,
        "plugin_id": "example.readonly",
        "display_name": "Example",
        "version": "1.0.0",
        "minimum_api_version": "1.0.0",
        "maximum_api_version": "1.0.0",
        "category": "command",
        "entry_point": "plugin:create_plugin",
        "description": "Measured manifest",
        "publisher": "Omega tests",
        "supported_operating_systems": ["windows"],
        "minimum_python_version": "3.11.0",
    }
    validator = PluginValidator(PluginConfiguration(), cache_size=2)
    payload = json.dumps(raw).encode()
    first = validator.parse(payload)
    assert validator.parse(payload) is first
    raw["description"] = "changed"
    changed = validator.parse(json.dumps(raw).encode())
    assert changed is not first
    assert validator.manifest_cache_size == 2
