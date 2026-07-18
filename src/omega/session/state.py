"""Data-only session states for Omega's terminal lifecycle."""

from enum import StrEnum


class SessionState(StrEnum):
    """Stable states used by the text-session state machine."""

    INACTIVE = "inactive"
    ACTIVE = "active"
    SHUTTING_DOWN = "shutting_down"
    TERMINATED = "terminated"
