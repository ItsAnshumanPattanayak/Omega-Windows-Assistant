"""Strict bounded JSON parsing shared by security-sensitive imports."""

from __future__ import annotations

import json
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from omega.core.exceptions import SecurityValidationError


@dataclass(frozen=True, slots=True)
class JsonSecurityLimits:
    maximum_bytes: int
    maximum_depth: int = 20
    maximum_items: int = 50_000

    def __post_init__(self) -> None:
        if any(
            isinstance(value, bool) or not isinstance(value, int) or value <= 0
            for value in (
                self.maximum_bytes,
                self.maximum_depth,
                self.maximum_items,
            )
        ):
            raise SecurityValidationError("JSON limits must be positive integers.")


def load_bounded_json(raw: str | bytes, limits: JsonSecurityLimits) -> Any:
    encoded = raw.encode("utf-8") if isinstance(raw, str) else raw
    if len(encoded) > limits.maximum_bytes:
        raise SecurityValidationError("JSON payload exceeds its byte limit.")

    def unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise SecurityValidationError("JSON contains a duplicate object key.")
            result[key] = value
        return result

    try:
        value = json.loads(
            encoded,
            object_pairs_hook=unique_object,
            parse_constant=_raise_nonfinite,
        )
    except SecurityValidationError:
        raise
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise SecurityValidationError("Payload is not valid UTF-8 JSON.") from error
    _validate_shape(value, limits, depth=0, counter=[0])
    return value


def _validate_shape(
    value: Any, limits: JsonSecurityLimits, *, depth: int, counter: list[int]
) -> None:
    if depth > limits.maximum_depth:
        raise SecurityValidationError("JSON payload nesting is excessive.")
    counter[0] += 1
    if counter[0] > limits.maximum_items:
        raise SecurityValidationError("JSON payload contains too many items.")
    if isinstance(value, Mapping):
        for key, item in value.items():
            if not isinstance(key, str) or "\x00" in key:
                raise SecurityValidationError("JSON object key is invalid.")
            _validate_shape(item, limits, depth=depth + 1, counter=counter)
        return
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        for item in value:
            _validate_shape(item, limits, depth=depth + 1, counter=counter)
        return
    if isinstance(value, float) and not math.isfinite(value):
        raise SecurityValidationError("JSON number must be finite.")
    if value is not None and not isinstance(value, (str, int, float, bool)):
        raise SecurityValidationError("JSON contains an unsupported value.")


def _raise_nonfinite(value: str) -> None:
    raise SecurityValidationError(f"JSON constant {value} is not permitted.")
