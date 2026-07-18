"""Structured result returned by the deterministic command parser."""

from __future__ import annotations

from dataclasses import dataclass, field

from omega.models import UserCommand


@dataclass
class CommandParseResult:
    command: UserCommand
    matched: bool
    requires_clarification: bool = False
    clarification_message: str | None = None
    missing_entities: list[str] = field(default_factory=list)
    ambiguous_entities: list[str] = field(default_factory=list)
    matched_pattern: str | None = None
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return {
            "command": self.command.to_dict(),
            "matched": self.matched,
            "requires_clarification": self.requires_clarification,
            "clarification_message": self.clarification_message,
            "missing_entities": list(self.missing_entities),
            "ambiguous_entities": list(self.ambiguous_entities),
            "matched_pattern": self.matched_pattern,
            "warnings": list(self.warnings),
        }
