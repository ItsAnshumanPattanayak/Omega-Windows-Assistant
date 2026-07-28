"""Best-effort bounded redaction for logs, exceptions, and diagnostics."""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Any

_SECRET_ASSIGNMENT = re.compile(
    r"(?i)\b(password|passwd|app[-_ ]?password|api[-_ ]?key|access[-_ ]?token|"
    r"refresh[-_ ]?token|client[-_ ]?secret|session[-_ ]?cookie|oauth[-_ ]?code|"
    r"authorization|token)\b\s*[:=]\s*([^\s,;\"'\]\[(){}]+)"
)
_BEARER = re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._~+/-]{4,}")
_PRIVATE_KEY = re.compile(
    r"-----BEGIN [^-\r\n]{0,40}PRIVATE KEY-----.*?"
    r"-----END [^-\r\n]{0,40}PRIVATE KEY-----",
    re.DOTALL,
)
_WINDOWS_PATH = re.compile(r"(?i)(?<![A-Za-z0-9])(?:[A-Z]:\\|\\\\)[^\r\n\t\"']+")
_SENSITIVE_KEYS = (
    "password",
    "passwd",
    "secret",
    "token",
    "authorization",
    "cookie",
    "credential",
    "private_key",
    "api_key",
    "oauth_code",
)


def redact_text(
    value: object, *, maximum_characters: int = 10_000, redact_paths: bool = False
) -> str:
    """Redact common secret shapes; this is defense-in-depth, not detection proof."""

    text = str(value)
    text = _PRIVATE_KEY.sub("[PRIVATE-KEY-REDACTED]", text)
    text = _BEARER.sub("Bearer [REDACTED]", text)
    text = _SECRET_ASSIGNMENT.sub(lambda match: f"{match.group(1)}=[REDACTED]", text)
    if redact_paths:
        text = _WINDOWS_PATH.sub("[PATH-REDACTED]", text)
    if len(text) > maximum_characters:
        return text[: maximum_characters - 13] + "...[truncated]"
    return text


def redact_value(value: Any, *, maximum_depth: int = 10) -> Any:
    if maximum_depth < 0:
        return "[DEPTH-REDACTED]"
    if isinstance(value, Mapping):
        return {
            str(key): (
                "[REDACTED]"
                if any(word in str(key).casefold() for word in _SENSITIVE_KEYS)
                else redact_value(item, maximum_depth=maximum_depth - 1)
            )
            for key, item in value.items()
        }
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [redact_value(item, maximum_depth=maximum_depth - 1) for item in value]
    return redact_text(value) if isinstance(value, str) else value


def safe_exception_message(error: BaseException) -> str:
    return redact_text(error, maximum_characters=2_000, redact_paths=True)
