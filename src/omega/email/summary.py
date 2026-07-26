"""Deterministic local summaries that never invent mailbox content."""

from __future__ import annotations

import re

from omega.email.models import EmailMessage

_SENTENCE = re.compile(r"(?<=[.!?])\s+")
_ACTION_WORDS = re.compile(
    r"\b(?:please|need|must|action|required|reply|respond|confirm|deadline|due)\b",
    re.IGNORECASE,
)


class DeterministicEmailSummarizer:
    """Select bounded source sentences without semantic inference or cloud calls."""

    def __init__(self, maximum_characters: int = 1_500) -> None:
        if not 100 <= maximum_characters <= 10_000:
            raise ValueError("Summary length must be between 100 and 10000.")
        self.maximum_characters = maximum_characters

    def summarize(self, message: EmailMessage) -> str:
        body = " ".join(message.plain_text_body.split())
        sentences = [item.strip() for item in _SENTENCE.split(body) if item.strip()]
        selected = sentences[:2]
        for sentence in sentences[2:]:
            if _ACTION_WORDS.search(sentence):
                selected.append(sentence)
                break
        content = (
            " ".join(selected) if selected else "No plain-text body was available."
        )
        prefix = (
            f"From: {message.sender}\nSubject: {message.subject or '(no subject)'}\n"
            f"Received: {message.received_at.isoformat()}\nSummary: "
        )
        available = max(0, self.maximum_characters - len(prefix))
        if len(content) > available:
            content = content[: max(0, available - 1)].rstrip() + "…"
        result = prefix + content
        if len(result) > self.maximum_characters:
            return result[: self.maximum_characters - 1].rstrip() + "…"
        return result
