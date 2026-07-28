"""Fail-closed validation for commands crossing an untrusted input boundary."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

from omega.core.exceptions import SecurityValidationError
from omega.security.configuration import SecurityConfiguration

_SHELL = re.compile(
    r"(?:&&|\|\||[|;<>`]|\$\(|%COMSPEC%|\bpowershell(?:\.exe)?\b|"
    r"\bcmd(?:\.exe)?\s*/[ck]|-encodedcommand\b|\b(?:eval|exec)\s*\()",
    re.IGNORECASE,
)
_DESTRUCTIVE = re.compile(
    r"\b(?:delete|remove|erase|wipe|format|shutdown|restart|send|archive|install|"
    r"grant|disable|हटाएँ|मिटाएँ|भेजें)\b",
    re.IGNORECASE,
)
_CYRILLIC = re.compile(r"[\u0400-\u04ff]")
_LATIN = re.compile(r"[A-Za-z]")


@dataclass(frozen=True, slots=True)
class ValidatedCommandInput:
    text: str
    shell_like: bool
    mixed_script: bool
    high_risk_ambiguous: bool


class SecurityInputValidator:
    def __init__(self, configuration: SecurityConfiguration) -> None:
        self.configuration = configuration

    def validate_command(self, text: str) -> ValidatedCommandInput:
        if not isinstance(text, str) or not text.strip():
            raise SecurityValidationError("A non-empty command is required.")
        if len(text) > self.configuration.maximum_command_characters:
            raise SecurityValidationError(
                "The command exceeds the configured security limit."
            )
        if len(text.split()) > self.configuration.maximum_command_tokens:
            raise SecurityValidationError("The command contains too many tokens.")
        if "\x00" in text:
            raise SecurityValidationError("Null bytes are not allowed in commands.")
        for character in text:
            if unicodedata.category(character) == "Cc" and character not in "\t\r\n":
                raise SecurityValidationError(
                    "Control characters are not allowed in commands."
                )
        shell_like = _SHELL.search(text) is not None
        mixed = _CYRILLIC.search(text) is not None and _LATIN.search(text) is not None
        risky = _DESTRUCTIVE.search(text) is not None
        return ValidatedCommandInput(text, shell_like, mixed, risky and mixed)


def contains_untrusted_instruction(value: str) -> bool:
    """Identify instruction-shaped content for labeling, never for execution."""

    lowered = value.casefold()
    return any(
        marker in lowered
        for marker in (
            "ignore previous instructions",
            "ignore system prompt",
            "bypass safety",
            "execute this command",
            "run powershell",
            "send this email automatically",
        )
    )
