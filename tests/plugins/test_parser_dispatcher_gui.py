from uuid import uuid4

import pytest

from omega.execution import PluginDispatcher
from omega.models import EntityType, IntentType, RiskLevel
from omega.plugins import PluginConfiguration, PluginPermission, PluginValidator
from omega.safety import RiskClassifier, SafeExecutionGateway, SafetyContext
from omega.understanding import CommandParser


@pytest.mark.parametrize(
    ("text", "intent"),
    [
        ("list plugins", IntentType.LIST_PLUGINS),
        ("show plugin example.readonly", IntentType.SHOW_PLUGIN),
        (
            "validate plugin package at Desktop/plugin.zip",
            IntentType.VALIDATE_PLUGIN_PACKAGE,
        ),
        ("install plugin from Desktop/plugin.zip", IntentType.INSTALL_PLUGIN),
        ("enable plugin example.readonly", IntentType.ENABLE_PLUGIN),
        ("disable plugin example.readonly", IntentType.DISABLE_PLUGIN),
        ("remove plugin example.readonly", IntentType.REMOVE_PLUGIN),
        (
            "show plugin permissions for example.readonly",
            IntentType.SHOW_PLUGIN_PERMISSIONS,
        ),
        (
            "grant create_note to plugin example.readonly",
            IntentType.GRANT_PLUGIN_PERMISSION,
        ),
        (
            "revoke create_note from plugin example.readonly",
            IntentType.REVOKE_PLUGIN_PERMISSION,
        ),
        ("reload plugin example.readonly", IntentType.RELOAD_PLUGIN),
        ("show failed plugins", IntentType.SHOW_FAILED_PLUGINS),
    ],
)
def test_plugin_parser_intents(text: str, intent: IntentType) -> None:
    result = CommandParser().parse(text, uuid4())
    assert result.matched and result.command.intent is intent


def test_plugin_entities_are_bounded_and_typed() -> None:
    parsed = CommandParser().parse(
        "grant create_note to plugin example.readonly", uuid4()
    )
    values = {entity.entity_type: entity.value for entity in parsed.command.entities}
    assert values[EntityType.PLUGIN] == "example.readonly"
    assert values[EntityType.PLUGIN_PERMISSION] == "create_note"


@pytest.mark.parametrize(
    ("intent", "risk"),
    [
        (IntentType.LIST_PLUGINS, RiskLevel.LOW),
        (IntentType.INSTALL_PLUGIN, RiskLevel.MEDIUM),
        (IntentType.REMOVE_PLUGIN, RiskLevel.HIGH),
    ],
)
def test_plugin_risk_classification(intent: IntentType, risk: RiskLevel) -> None:
    from omega.models import Action, UserCommand

    command = UserCommand("[redacted]", intent=intent, session_id=uuid4())
    action = Action(command.command_id, intent, risk_level=risk)
    assert (
        RiskClassifier().classify(SafetyContext(command, action, command.session_id))
        is risk
    )


class _ListOnlyManager:
    def discover(self) -> tuple[object, ...]:
        return ()

    def clear_session(self) -> None:
        return None


def test_dispatcher_routes_read_only_list_through_gateway() -> None:
    dispatcher = PluginDispatcher(_ListOnlyManager(), SafeExecutionGateway())  # type: ignore[arg-type]
    result = dispatcher.dispatch(CommandParser().parse("list plugins", uuid4()))
    assert result is not None
    assert result.result.success
    assert result.user_message == "No plugins discovered."


def test_manifest_permissions_do_not_include_forbidden_capabilities() -> None:
    forbidden = {
        "shell_execution",
        "arbitrary_network_access",
        "credential_access",
        "raw_database_access",
        "safety_bypass",
        "confirmation_bypass",
        "automatic_email_send",
        "automatic_calendar_mutation",
    }
    assert forbidden.isdisjoint(permission.value for permission in PluginPermission)


def test_plugin_configuration_has_no_private_tracked_path() -> None:
    value = PluginConfiguration()
    assert value.user_plugin_directory is None
    assert value.development_plugin_directory is None
    assert PluginValidator(value).configuration is value
