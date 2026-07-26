"""Strict scalar-only workflow substitution and deterministic conditions."""

from __future__ import annotations

import re
from collections.abc import Mapping

from omega.models._serialization import JsonValue, validate_json_value
from omega.workflows.exceptions import WorkflowValidationError
from omega.workflows.models import ConditionOperator, WorkflowCondition

_REFERENCE = re.compile(r"\$\{([A-Za-z][A-Za-z0-9_.]{0,127})\}")


def resolve_reference(reference: str, values: Mapping[str, JsonValue]) -> JsonValue:
    if reference not in values:
        raise WorkflowValidationError(f"Workflow variable {reference} is missing.")
    return validate_json_value(values[reference], "workflow variable")


def substitute(
    value: JsonValue, values: Mapping[str, JsonValue], maximum: int
) -> JsonValue:
    if not isinstance(value, str):
        return validate_json_value(value, "workflow value")
    exact = _REFERENCE.fullmatch(value)
    if exact:
        resolved = resolve_reference(exact.group(1), values)
        if isinstance(resolved, str) and len(resolved) > maximum:
            raise WorkflowValidationError(
                "Substituted workflow text exceeds its bound."
            )
        return resolved

    def replacement(match: re.Match[str]) -> str:
        item = resolve_reference(match.group(1), values)
        if not isinstance(item, str | int | bool):
            raise WorkflowValidationError(
                "Only scalar variables can be formatted into text."
            )
        return str(item)

    rendered = _REFERENCE.sub(replacement, value)
    if len(rendered) > maximum:
        raise WorkflowValidationError("Substituted workflow text exceeds its bound.")
    return rendered


def evaluate(
    condition: WorkflowCondition, values: Mapping[str, JsonValue], maximum: int
) -> bool:
    left = substitute(condition.left, values, maximum)
    right = substitute(condition.right, values, maximum)
    op = condition.operator
    if op is ConditionOperator.EQUALS:
        return left == right
    if op is ConditionOperator.NOT_EQUALS:
        return left != right
    if op in {
        ConditionOperator.CONTAINS,
        ConditionOperator.STARTS_WITH,
        ConditionOperator.ENDS_WITH,
    }:
        if not isinstance(left, str) or not isinstance(right, str):
            raise WorkflowValidationError("Text comparison requires string values.")
        return (
            right in left
            if op is ConditionOperator.CONTAINS
            else (
                left.startswith(right)
                if op is ConditionOperator.STARTS_WITH
                else left.endswith(right)
            )
        )
    if op in {ConditionOperator.GREATER_THAN, ConditionOperator.LESS_THAN}:
        if (
            isinstance(left, bool)
            or isinstance(right, bool)
            or not isinstance(left, int | float)
            or not isinstance(right, int | float)
        ):
            raise WorkflowValidationError("Numeric comparison requires numbers.")
        return left > right if op is ConditionOperator.GREATER_THAN else left < right
    if op is ConditionOperator.IS_EMPTY:
        return left in (None, "", [])
    if op is ConditionOperator.IS_NOT_EMPTY:
        return left not in (None, "", [])
    if not isinstance(left, bool):
        raise WorkflowValidationError("Boolean comparison requires a boolean.")
    return left if op is ConditionOperator.IS_TRUE else not left
