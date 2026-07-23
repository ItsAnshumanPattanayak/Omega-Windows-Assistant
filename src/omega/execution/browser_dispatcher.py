"""Browser action adapter protected by Omega's central execution gateway."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from omega.browser import BrowserManager, UrlValidator, redact_url
from omega.models import (
    Action,
    ActionResult,
    ConfirmationStatus,
    IntentType,
    PermissionDecision,
    RiskLevel,
    UserCommand,
)
from omega.models._serialization import JsonValue
from omega.safety import (
    ConfirmationSpec,
    GatewayDispatchResult,
    ResourceFingerprint,
    SafeExecutionGateway,
    SafetyContext,
)
from omega.understanding.result import CommandParseResult

_BROWSER_INTENTS = frozenset(
    {
        IntentType.OPEN_BROWSER,
        IntentType.CLOSE_BROWSER,
        IntentType.OPEN_WEBSITE,
        IntentType.SEARCH_WEB,
        IntentType.OPEN_NEW_TAB,
        IntentType.CLOSE_TAB,
        IntentType.SWITCH_TAB,
        IntentType.LIST_TABS,
        IntentType.REFRESH_PAGE,
        IntentType.GO_BACK,
        IntentType.GO_FORWARD,
        IntentType.GET_PAGE_INFORMATION,
        IntentType.FIND_TEXT_ON_PAGE,
        IntentType.OPEN_BOOKMARK,
        IntentType.SAVE_BOOKMARK,
    }
)
_LOW = frozenset(
    {
        IntentType.CLOSE_TAB,
        IntentType.LIST_TABS,
        IntentType.REFRESH_PAGE,
        IntentType.GO_BACK,
        IntentType.GO_FORWARD,
        IntentType.GET_PAGE_INFORMATION,
        IntentType.FIND_TEXT_ON_PAGE,
    }
)
_HIGH = frozenset({IntentType.CLOSE_BROWSER, IntentType.SAVE_BOOKMARK})


@dataclass(frozen=True)
class BrowserDispatchResult:
    """Typed gateway result for a browser proposal."""

    command: UserCommand
    action: Action
    result: ActionResult

    @property
    def user_message(self) -> str:
        return self.result.user_message

    @classmethod
    def from_gateway(cls, value: GatewayDispatchResult) -> BrowserDispatchResult:
        return cls(value.command, value.action, value.result)


class BrowserActionDispatcher:
    """Translate parsed browser intents and submit every action to the gateway."""

    def __init__(
        self,
        manager: BrowserManager,
        gateway: SafeExecutionGateway,
        validator: UrlValidator,
    ) -> None:
        self.manager = manager
        self.gateway = gateway
        self.validator = validator

    def dispatch(self, parsed: CommandParseResult) -> BrowserDispatchResult | None:
        command = parsed.command
        if (
            not parsed.matched
            or parsed.requires_clarification
            or command.intent not in _BROWSER_INTENTS
        ):
            return None
        parameters = self._parameters(command)
        action = Action(
            command_id=command.command_id,
            intent=command.intent,
            parameters=parameters,
            risk_level=self._risk(command.intent),
            permission_decision=PermissionDecision.ALLOW,
            confirmation_status=ConfirmationStatus.NOT_REQUIRED,
            requires_confirmation=False,
        )
        logical_target = self._logical_target(command)
        context = SafetyContext(
            command=command,
            action=action,
            session_id=command.session_id or UUID(int=0),
            logical_source=logical_target,
            target_type="browser",
            additional_context={"browser_action": True},
        )
        confirmation = self._confirmation(command, logical_target)
        fingerprint = (
            ResourceFingerprint(
                "browser_session",
                f"{command.session_id}:{logical_target}",
                self.manager.state.value == "active",
            )
            if confirmation is not None
            else None
        )
        dispatched = self.gateway.submit(
            context,
            lambda: self._execute(command, action),
            confirmation=confirmation,
            fingerprint=fingerprint,
            revalidator=lambda: fingerprint,
        )
        return BrowserDispatchResult.from_gateway(dispatched)

    def shutdown(self) -> None:
        self.manager.shutdown()

    def _execute(self, command: UserCommand, action: Action) -> ActionResult:
        intent = command.intent
        action_id, command_id = action.action_id, command.command_id
        if intent is IntentType.OPEN_BROWSER:
            return self.manager.open_browser(action_id, command_id)
        if intent is IntentType.CLOSE_BROWSER:
            return self.manager.close_browser(action_id, command_id)
        if intent is IntentType.OPEN_WEBSITE:
            return self.manager.navigate(
                action_id, command_id, self._required(command, "url"), new_tab=True
            )
        if intent is IntentType.SEARCH_WEB:
            return self.manager.search(
                action_id, command_id, self._required(command, "search_query")
            )
        if intent is IntentType.OPEN_NEW_TAB:
            return self.manager.open_new_tab(action_id, command_id)
        if intent in {IntentType.CLOSE_TAB, IntentType.SWITCH_TAB}:
            tab_id = self.manager.resolve_tab_id(self._required(command, "tab"))
            if intent is IntentType.CLOSE_TAB:
                return self.manager.close_tab(action_id, command_id, tab_id)
            return self.manager.switch_tab(action_id, command_id, tab_id)
        if intent is IntentType.LIST_TABS:
            return self.manager.list_tabs(action_id, command_id)
        if intent is IntentType.REFRESH_PAGE:
            return self.manager.refresh(action_id, command_id)
        if intent is IntentType.GO_BACK:
            return self.manager.go_back(action_id, command_id)
        if intent is IntentType.GO_FORWARD:
            return self.manager.go_forward(action_id, command_id)
        if intent is IntentType.GET_PAGE_INFORMATION:
            return self.manager.page_information(action_id, command_id)
        if intent is IntentType.FIND_TEXT_ON_PAGE:
            return self.manager.find_text(
                action_id, command_id, self._required(command, "text_content")
            )
        if intent is IntentType.OPEN_BOOKMARK:
            return self.manager.open_bookmark(
                action_id, command_id, self._required(command, "bookmark_name")
            )
        return self.manager.save_current_bookmark(
            action_id, command_id, self._required(command, "bookmark_name")
        )

    def _parameters(self, command: UserCommand) -> dict[str, JsonValue]:
        if command.intent is IntentType.OPEN_WEBSITE:
            raw = self._required(command, "url")
            try:
                return {"url": self.validator.validate(raw).redacted_url}
            except Exception:
                return {"url": redact_url(raw)}
        if command.intent is IntentType.SEARCH_WEB:
            return {
                "search_engine": self.manager.configuration.default_search_engine,
                "query_length": len(self._required(command, "search_query")),
            }
        for name in ("tab", "bookmark_name"):
            value = self._optional(command, name)
            if value is not None:
                return {name: value}
        if command.intent is IntentType.FIND_TEXT_ON_PAGE:
            return {"text_length": len(self._required(command, "text_content"))}
        return {}

    def _logical_target(self, command: UserCommand) -> str:
        if command.intent is IntentType.OPEN_WEBSITE:
            raw = self._required(command, "url")
            try:
                return self.validator.validate(raw).redacted_url
            except Exception:
                return "[invalid-url]"
        if command.intent is IntentType.SEARCH_WEB:
            return self.manager.configuration.default_search_engine
        return (
            self._optional(command, "tab")
            or self._optional(command, "bookmark_name")
            or "Omega-controlled browser"
        )

    def _confirmation(
        self, command: UserCommand, target: str
    ) -> ConfirmationSpec | None:
        if command.intent is IntentType.CLOSE_BROWSER:
            return ConfirmationSpec(
                target,
                "Closing the Omega browser may discard unsaved page state. Type "
                '"confirm close browser" to continue.',
                "confirm close browser",
                "cancel close browser",
            )
        if command.intent is IntentType.SAVE_BOOKMARK:
            name = self._required(command, "bookmark_name")
            exact = f"confirm save bookmark {name}"
            return ConfirmationSpec(
                target,
                f'Saving bookmark "{name}" changes Omega bookmark data. '
                f'Type "{exact}" to continue.',
                exact,
                f"cancel save bookmark {name}",
            )
        return None

    @staticmethod
    def _risk(intent: IntentType) -> RiskLevel:
        if intent in _LOW:
            return RiskLevel.LOW
        if intent in _HIGH:
            return RiskLevel.HIGH
        return RiskLevel.MEDIUM

    @staticmethod
    def _optional(command: UserCommand, name: str) -> str | None:
        values = [
            entity.value
            for entity in command.entities
            if entity.name == name and isinstance(entity.value, str)
        ]
        return values[0] if len(values) == 1 else None

    @classmethod
    def _required(cls, command: UserCommand, name: str) -> str:
        value = cls._optional(command, name)
        if value is None:
            raise ValueError(f"Missing browser parameter: {name}")
        return value
