"""Validated permission configuration and ordered default-deny policy engine."""

from __future__ import annotations

import json
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from omega.core.exceptions import PolicyConfigurationError
from omega.models import IntentType, PermissionDecision, RiskLevel
from omega.safety.classifier import RiskClassifier
from omega.safety.models import SafetyContext, SafetyEvaluation
from omega.safety.policies import (
    DEFAULT_POLICIES,
    PolicyDisposition,
    PolicyResult,
    SafetyPolicy,
)
from omega.safety.protected_resources import ProtectedResourceEvaluator
from omega.utils.paths import config_dir

_RISK_ORDER = {
    RiskLevel.LOW: 0,
    RiskLevel.MEDIUM: 1,
    RiskLevel.HIGH: 2,
    RiskLevel.CRITICAL: 3,
}

_RECOVERABLE_DELETION_INTENTS = frozenset(
    {
        IntentType.DELETE_FILE,
        IntentType.DELETE_FOLDER,
    }
)


@dataclass(frozen=True)
class ActionPermissionRule:
    """Static permission rule for one typed Omega intent."""

    enabled: bool
    maximum_risk: RiskLevel = RiskLevel.HIGH
    requires_confirmation: bool = False

    @classmethod
    def from_mapping(
        cls,
        intent: IntentType,
        values: Mapping[str, Any],
    ) -> ActionPermissionRule:
        enabled = values.get("enabled", False)
        required = values.get("requires_confirmation", False)

        if not isinstance(enabled, bool) or not isinstance(required, bool):
            raise PolicyConfigurationError(
                f"Permission rule {intent.value} contains an invalid boolean."
            )

        try:
            maximum = RiskLevel(values.get("maximum_risk", "high"))
        except ValueError as error:
            raise PolicyConfigurationError(
                f"Permission rule {intent.value} contains an invalid risk."
            ) from error

        if intent in _RECOVERABLE_DELETION_INTENTS:
            if enabled and not required:
                raise PolicyConfigurationError(
                    f"Recoverable operation {intent.value} must require confirmation."
                )

            if enabled and maximum is not RiskLevel.CRITICAL:
                raise PolicyConfigurationError(
                    f"Recoverable operation {intent.value} must allow critical risk."
                )

        return cls(
            enabled=enabled,
            maximum_risk=maximum,
            requires_confirmation=required,
        )


@dataclass(frozen=True)
class PermissionConfiguration:
    """Static restrictions that may tighten but never weaken safety boundaries."""

    default_decision: PermissionDecision
    actions: Mapping[IntentType, ActionPermissionRule]

    def __post_init__(self) -> None:
        if self.default_decision is not PermissionDecision.DENY:
            raise PolicyConfigurationError(
                "The default permission decision must remain deny."
            )

        if len(self.actions) != len(set(self.actions)):
            raise PolicyConfigurationError("Permission rules must not be duplicated.")

    @classmethod
    def defaults(cls) -> PermissionConfiguration:
        confirmation_intents = {
            IntentType.CLOSE_APPLICATION,
            IntentType.MOVE_FILE,
            IntentType.MOVE_FOLDER,
            IntentType.DELETE_FILE,
            IntentType.DELETE_FOLDER,
            IntentType.UNDO_LAST_ACTION,
            IntentType.CLEAR_HISTORY,
            IntentType.CLOSE_BROWSER,
            IntentType.SAVE_BOOKMARK,
        }

        supported = {
            intent: ActionPermissionRule(
                enabled=True,
                maximum_risk=(
                    RiskLevel.CRITICAL
                    if intent in _RECOVERABLE_DELETION_INTENTS
                    else RiskLevel.HIGH
                ),
                requires_confirmation=intent in confirmation_intents,
            )
            for intent in IntentType
            if intent
            not in {
                IntentType.UNKNOWN,
                IntentType.HELP,
                IntentType.ACTIVATE_ASSISTANT,
                IntentType.SHUTDOWN_ASSISTANT,
            }
        }

        return cls(
            default_decision=PermissionDecision.DENY,
            actions=supported,
        )

    @classmethod
    def from_mapping(
        cls,
        values: Mapping[str, Any],
    ) -> PermissionConfiguration:
        try:
            default = PermissionDecision(values.get("default_decision", "deny"))
        except ValueError as error:
            raise PolicyConfigurationError(
                "Invalid default permission decision."
            ) from error

        raw_actions = values.get("actions")

        if not isinstance(raw_actions, Mapping):
            raise PolicyConfigurationError("permissions.actions must be a mapping.")

        actions: dict[IntentType, ActionPermissionRule] = {}

        for raw_intent, raw_rule in raw_actions.items():
            try:
                intent = IntentType(raw_intent)
            except (TypeError, ValueError) as error:
                raise PolicyConfigurationError(
                    f"Unknown intent in permission configuration: {raw_intent}"
                ) from error

            if intent in actions:
                raise PolicyConfigurationError(
                    f"Duplicate permission rule: {intent.value}"
                )

            if not isinstance(raw_rule, Mapping):
                raise PolicyConfigurationError(
                    f"Permission rule {intent.value} must be an object."
                )

            actions[intent] = ActionPermissionRule.from_mapping(
                intent,
                raw_rule,
            )

        return cls(
            default_decision=default,
            actions=actions,
        )

    @classmethod
    def from_file(
        cls,
        path: Path | None = None,
    ) -> PermissionConfiguration:
        selected = path or config_dir() / "permissions.json"

        def unique_object(
            pairs: list[tuple[str, Any]],
        ) -> dict[str, Any]:
            result: dict[str, Any] = {}

            for key, value in pairs:
                if key in result:
                    raise PolicyConfigurationError(
                        f"Duplicate configuration key: {key}"
                    )

                result[key] = value

            return result

        try:
            raw = json.loads(
                selected.read_text(encoding="utf-8"),
                object_pairs_hook=unique_object,
            )
        except (OSError, json.JSONDecodeError) as error:
            raise PolicyConfigurationError(
                "Permission configuration is invalid."
            ) from error

        if not isinstance(raw, Mapping):
            raise PolicyConfigurationError(
                "Permission configuration must be an object."
            )

        return cls.from_mapping(raw)


class PermissionPolicyEngine:
    """Evaluate every safety policy with deterministic deny-first precedence."""

    def __init__(
        self,
        *,
        policies: Iterable[SafetyPolicy] = DEFAULT_POLICIES,
        configuration: PermissionConfiguration | None = None,
        classifier: RiskClassifier | None = None,
        protected_resources: ProtectedResourceEvaluator | None = None,
    ) -> None:
        ordered = tuple(
            sorted(
                policies,
                key=lambda policy: (
                    policy.priority,
                    policy.policy_id,
                ),
            )
        )

        ids = [policy.policy_id for policy in ordered]

        if len(ids) != len(set(ids)):
            raise PolicyConfigurationError("Safety policy IDs must be unique.")

        self.policies = ordered
        self.configuration = configuration or PermissionConfiguration.defaults()
        self.classifier = classifier or RiskClassifier()
        self.protected_resources = protected_resources or ProtectedResourceEvaluator()

    def evaluate(
        self,
        context: SafetyContext,
        *,
        confirmation_prompt: str | None = None,
    ) -> SafetyEvaluation:
        protected = self.protected_resources.evaluate(context)
        augmented = context

        if protected.denied and not context.additional_context.get(
            "protected_resource"
        ):
            augmented = SafetyContext(
                command=context.command,
                action=context.action,
                session_id=context.session_id,
                platform=context.platform,
                application_id=context.application_id,
                source_path=context.source_path,
                destination_path=context.destination_path,
                logical_source=context.logical_source,
                logical_destination=context.logical_destination,
                target_exists=context.target_exists,
                target_type=context.target_type,
                requested_at=context.requested_at,
                additional_context={
                    **context.additional_context,
                    "protected_resource": True,
                },
            )

        risk = self.classifier.classify(augmented)

        results = [
            policy.evaluate(
                augmented,
                risk_level=risk,
                protected=protected,
            )
            for policy in self.policies
        ]

        applicable = [
            item
            for item in results
            if item.disposition is not PolicyDisposition.NOT_APPLICABLE
        ]

        configured_denial = self._configuration_denial(
            augmented,
            risk,
        )

        if configured_denial is not None:
            applicable.append(configured_denial)
        else:
            rule = self.configuration.actions.get(augmented.action.intent)

            if rule is not None and rule.requires_confirmation:
                applicable.append(
                    PolicyResult(
                        "SAFETY-CONFIG-CONFIRM-001",
                        PolicyDisposition.REQUIRE_CONFIRMATION,
                        "CONFIGURED_CONFIRMATION_REQUIRED",
                        "Configuration requires explicit confirmation.",
                        "Exact confirmation is required for that operation.",
                    )
                )

        denials = [
            item for item in applicable if item.disposition is PolicyDisposition.DENY
        ]

        confirmations = [
            item
            for item in applicable
            if item.disposition is PolicyDisposition.REQUIRE_CONFIRMATION
        ]

        allows = [
            item for item in applicable if item.disposition is PolicyDisposition.ALLOW
        ]

        if denials:
            selected = self._select_denial(denials)
            decision = PermissionDecision.DENY
        elif confirmations:
            selected = confirmations[0]
            decision = PermissionDecision.REQUIRE_CONFIRMATION
        elif allows:
            selected = allows[0]
            decision = PermissionDecision.ALLOW
        else:
            selected = PolicyResult(
                "SAFETY-DEFAULT-DENY-001",
                PolicyDisposition.DENY,
                "DEFAULT_DENY",
                "No explicit allow policy applied.",
                "Omega does not have permission to perform that operation.",
            )
            applicable.append(selected)
            decision = PermissionDecision.DENY

        prompt = (
            confirmation_prompt
            if decision is PermissionDecision.REQUIRE_CONFIRMATION
            else None
        )

        if decision is PermissionDecision.REQUIRE_CONFIRMATION and not prompt:
            prompt = "Exact confirmation is required before Omega can continue."

        return SafetyEvaluation(
            decision=decision,
            risk_level=risk,
            reason_code=selected.reason_code,
            reason=selected.reason,
            user_message=selected.user_message,
            requires_confirmation=(decision is PermissionDecision.REQUIRE_CONFIRMATION),
            confirmation_prompt=prompt,
            matched_policies=tuple(item.policy_id for item in applicable),
            denied_by=(
                selected.policy_id if decision is PermissionDecision.DENY else None
            ),
        )

    def _configuration_denial(
        self,
        context: SafetyContext,
        risk: RiskLevel,
    ) -> PolicyResult | None:
        rule = self.configuration.actions.get(context.action.intent)

        if rule is None or not rule.enabled:
            return PolicyResult(
                "SAFETY-CONFIG-DENY-001",
                PolicyDisposition.DENY,
                "ACTION_DISABLED",
                "The operation is disabled by configuration.",
                "Omega does not have permission to perform that operation.",
            )

        if _RISK_ORDER[risk] > _RISK_ORDER[rule.maximum_risk]:
            return PolicyResult(
                "SAFETY-CONFIG-RISK-001",
                PolicyDisposition.DENY,
                "CONFIGURED_RISK_LIMIT",
                "The action exceeds its configured maximum risk.",
                "Omega does not have permission to perform that operation.",
            )

        return None

    @staticmethod
    def _select_denial(
        denials: list[PolicyResult],
    ) -> PolicyResult:
        for reason in (
            "ARBITRARY_SHELL_DENIED",
            "PROTECTED_APPLICATION",
            "PROTECTED_PATH",
            "SHELL_INJECTION_REJECTED",
            "UNSAFE_EXTENSION_DENIED",
        ):
            selected = next(
                (item for item in denials if item.reason_code == reason),
                None,
            )

            if selected is not None:
                return selected

        return denials[0]
