"""Typed, short-lived clarification state for application-name input."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from omega.models import CommandSource


@dataclass(frozen=True)
class PendingApplicationClarification:
    """Bind one application proposal to one active session and expiry time."""

    session_id: UUID
    application_id: str
    display_name: str
    source: CommandSource
    expires_at: float

    def is_expired(self, now: float) -> bool:
        """Return whether this clarification may no longer accept a reply."""

        return now >= self.expires_at
