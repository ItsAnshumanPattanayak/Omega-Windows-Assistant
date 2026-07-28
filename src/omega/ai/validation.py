"""Validation for untrusted provider output and generated proposals."""

from __future__ import annotations

import json
import re
from collections.abc import Collection

from omega.ai.exceptions import AiValidationError
from omega.ai.models import AiGenerationResult, json_object
from omega.models._serialization import JsonValue

_UNSAFE_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_SHELL = re.compile(
    r"(?i)(?:\bos\.system\b|\bshell\s*=\s*true\b|\bcmd\s+/c\b|"
    r"\bpowershell\b|\bsubprocess\b|\beval\s*\(|\bexec\s*\()"
)


class AiResponseValidator:
    def __init__(self, maximum_characters: int) -> None:
        self.maximum_characters = maximum_characters

    def validate_text(
        self,
        result: AiGenerationResult,
        *,
        allowed_citations: Collection[str] = (),
    ) -> AiGenerationResult:
        if not result.text.strip():
            raise AiValidationError("The local AI provider returned empty text.")
        try:
            result.text.encode("utf-8")
        except UnicodeEncodeError as error:
            raise AiValidationError(
                "The local AI response is not valid UTF-8 text."
            ) from error
        if len(result.text) > self.maximum_characters:
            raise AiValidationError("The local AI response exceeded its size limit.")
        if _UNSAFE_CONTROL.search(result.text):
            raise AiValidationError("The local AI response contains control data.")
        unknown = set(result.citations) - set(allowed_citations)
        if unknown:
            raise AiValidationError("The local AI response contains invalid citations.")
        return result

    def structured_object(
        self,
        text: str,
        *,
        allowed_fields: Collection[str],
        required_fields: Collection[str] = (),
    ) -> dict[str, JsonValue]:
        if len(text) > self.maximum_characters or _UNSAFE_CONTROL.search(text):
            raise AiValidationError("Structured AI output is invalid or oversized.")
        try:
            value = json.loads(text)
        except (json.JSONDecodeError, UnicodeError) as error:
            raise AiValidationError(
                "Structured AI output is not valid JSON."
            ) from error
        result = json_object(value)
        if set(result) - set(allowed_fields):
            raise AiValidationError("Structured AI output contains unknown fields.")
        if not set(required_fields).issubset(result):
            raise AiValidationError("Structured AI output is missing required fields.")
        return result

    def workflow_proposal(
        self, text: str, *, allowed_step_types: Collection[str]
    ) -> dict[str, JsonValue]:
        result = self.structured_object(
            text,
            allowed_fields={"name", "description", "steps"},
            required_fields={"name", "steps"},
        )
        steps = result["steps"]
        if not isinstance(steps, list) or len(steps) > 50:
            raise AiValidationError("The workflow proposal has invalid steps.")
        for step in steps:
            if not isinstance(step, dict) or set(step) - {"type", "arguments"}:
                raise AiValidationError("A workflow proposal step is malformed.")
            step_type = step.get("type")
            if step_type not in allowed_step_types:
                raise AiValidationError("The workflow proposal uses an unknown step.")
            if _SHELL.search(json.dumps(step, sort_keys=True)):
                raise AiValidationError("Executable workflow content is prohibited.")
        return result

    def command_proposal(
        self, text: str, *, known_intents: Collection[str]
    ) -> dict[str, JsonValue]:
        result = self.structured_object(
            text,
            allowed_fields={
                "intent",
                "entities",
                "confidence",
                "explanation",
                "clarify",
            },
            required_fields={
                "intent",
                "entities",
                "confidence",
                "explanation",
                "clarify",
            },
        )
        if result["intent"] not in known_intents:
            raise AiValidationError(
                "The AI command proposal contains an unknown intent."
            )
        if _SHELL.search(text):
            raise AiValidationError("Executable command proposals are prohibited.")
        entities = result["entities"]
        if not isinstance(entities, list) or len(entities) > 20:
            raise AiValidationError("The AI command proposal entities are invalid.")
        if any(
            not isinstance(item, dict) or set(item) - {"name", "value", "entity_type"}
            for item in entities
        ):
            raise AiValidationError("An AI command proposal entity is malformed.")
        confidence = result["confidence"]
        if (
            isinstance(confidence, bool)
            or not isinstance(confidence, (int, float))
            or not 0.0 <= confidence <= 1.0
        ):
            raise AiValidationError("AI command confidence is invalid.")
        if not isinstance(result["clarify"], bool) or not isinstance(
            result["explanation"], str
        ):
            raise AiValidationError("AI command explanation is invalid.")
        return result
