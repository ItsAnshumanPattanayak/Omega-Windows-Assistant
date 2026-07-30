"""Typed presentation states and observable state transitions for Omega V2."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from threading import RLock
from types import MappingProxyType
from typing import Final

from omega.core.exceptions import GuiError
from omega.utils.logger import get_logger


class GuiStateTransitionError(GuiError):
    """Raised when a presentation-state transition is not allowed."""


class GuiState(StrEnum):
    """Stable presentation identifiers independent of any widget toolkit."""

    SLEEPING = "sleeping"
    IDLE = "idle"
    LISTENING = "listening"
    UNDERSTANDING = "understanding"
    PLANNING = "planning"
    WAITING_FOR_CONFIRMATION = "waiting_for_confirmation"
    EXECUTING = "executing"
    SPEAKING = "speaking"
    COMPLETED = "completed"
    ERROR = "error"
    PERMISSION_REQUIRED = "permission_required"
    EMERGENCY_STOPPED = "emergency_stopped"


@dataclass(frozen=True, slots=True)
class GuiStateMetadata:
    """Accessible presentation hints for one GUI state."""

    label: str
    description: str
    visual_intensity: float
    expects_user_input: bool = False
    execution_active: bool = False
    emergency_stop_relevant: bool = False
    accessibility_text: str = ""


STATE_METADATA: Final = MappingProxyType(
    {
        GuiState.SLEEPING: GuiStateMetadata(
            "Sleeping", "Omega is resting and waiting to be started.", 0.15
        ),
        GuiState.IDLE: GuiStateMetadata(
            "Idle", "Omega is ready for a local interaction.", 0.25, True
        ),
        GuiState.LISTENING: GuiStateMetadata(
            "Listening",
            "Listening demonstration only; no microphone is active.",
            0.55,
            True,
            accessibility_text=(
                "Listening demonstration. Microphone capture is disabled."
            ),
        ),
        GuiState.UNDERSTANDING: GuiStateMetadata(
            "Understanding", "Interpreting the current demonstration input.", 0.65
        ),
        GuiState.PLANNING: GuiStateMetadata(
            "Planning", "Preparing a safe action proposal.", 0.72
        ),
        GuiState.WAITING_FOR_CONFIRMATION: GuiStateMetadata(
            "Waiting for confirmation",
            "A future action would require deliberate confirmation.",
            0.45,
            True,
            emergency_stop_relevant=True,
        ),
        GuiState.EXECUTING: GuiStateMetadata(
            "Executing",
            "Execution presentation only; Phase 1 starts no system action.",
            0.9,
            execution_active=True,
            emergency_stop_relevant=True,
        ),
        GuiState.SPEAKING: GuiStateMetadata(
            "Speaking", "Speech presentation only; text-to-speech is disabled.", 0.7
        ),
        GuiState.COMPLETED: GuiStateMetadata(
            "Completed", "The current demonstration flow is complete.", 0.3, True
        ),
        GuiState.ERROR: GuiStateMetadata(
            "Error", "Omega entered a safe presentation error state.", 0.2, True
        ),
        GuiState.PERMISSION_REQUIRED: GuiStateMetadata(
            "Permission required",
            "A future capability would require explicit permission.",
            0.35,
            True,
            emergency_stop_relevant=True,
        ),
        GuiState.EMERGENCY_STOPPED: GuiStateMetadata(
            "Emergency stopped",
            (
                "Local demonstration activity has stopped. "
                "No process termination was claimed."
            ),
            0.0,
            True,
            accessibility_text=(
                "Emergency stopped. Local demonstration state is cleared."
            ),
        ),
    }
)

StateListener = Callable[[GuiState, GuiStateMetadata], None]


class GuiStateManager:
    """Own presentation state and notify listeners without widget coupling."""

    def __init__(self, initial_state: GuiState = GuiState.SLEEPING) -> None:
        if initial_state not in STATE_METADATA:
            raise GuiStateTransitionError("The initial GUI state is not supported.")
        self._state = initial_state
        self._listeners: list[StateListener] = []
        self._lock = RLock()
        self._logger = get_logger("gui_v2.state")

    @property
    def state(self) -> GuiState:
        with self._lock:
            return self._state

    @property
    def metadata(self) -> GuiStateMetadata:
        return STATE_METADATA[self.state]

    def subscribe(self, listener: StateListener) -> Callable[[], None]:
        """Register a listener and return an idempotent unsubscribe callback."""

        with self._lock:
            if listener not in self._listeners:
                self._listeners.append(listener)

        def unsubscribe() -> None:
            with self._lock:
                if listener in self._listeners:
                    self._listeners.remove(listener)

        return unsubscribe

    def set_state(self, state: GuiState, *, demo_override: bool = False) -> bool:
        """Apply one validated transition; return false for an idempotent repeat."""

        if state not in STATE_METADATA:
            raise GuiStateTransitionError("The requested GUI state is not supported.")
        with self._lock:
            previous = self._state
            if previous is state:
                return False
            if (
                previous is GuiState.EMERGENCY_STOPPED
                and state not in {GuiState.SLEEPING, GuiState.IDLE}
                and not demo_override
            ):
                raise GuiStateTransitionError(
                    "Emergency-stopped presentation must reset before continuing."
                )
            self._state = state
            listeners = tuple(self._listeners)
        metadata = STATE_METADATA[state]
        self._logger.info(
            "Omega V2 GUI state changed from %s to %s.", previous.value, state.value
        )
        for listener in listeners:
            listener(state, metadata)
        return True

    def emergency_stop(self) -> bool:
        """Immediately enter the local emergency-stopped presentation state."""

        return self.set_state(GuiState.EMERGENCY_STOPPED)

    def reset(self) -> bool:
        """Return to the safe sleeping state."""

        return self.set_state(GuiState.SLEEPING)
