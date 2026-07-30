"""Toolkit-neutral coordination for the Omega V2 presentation foundation."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from omega.gui_v2.state import GuiState, GuiStateManager, GuiStateMetadata


@dataclass(frozen=True, slots=True)
class V2ViewSnapshot:
    state: GuiState
    metadata: GuiStateMetadata
    user_command: str
    omega_response: str


ViewListener = Callable[[V2ViewSnapshot], None]


class OmegaV2ViewModel:
    """Coordinate Phase 1 display text and presentation-state controls."""

    def __init__(self, state_manager: GuiStateManager) -> None:
        self.state_manager = state_manager
        self.user_command = ""
        self.omega_response = ""
        self._listeners: list[ViewListener] = []
        self._unsubscribe_state = state_manager.subscribe(self._state_changed)

    @property
    def snapshot(self) -> V2ViewSnapshot:
        return V2ViewSnapshot(
            self.state_manager.state,
            self.state_manager.metadata,
            self.user_command,
            self.omega_response,
        )

    def subscribe(self, listener: ViewListener) -> Callable[[], None]:
        if listener not in self._listeners:
            self._listeners.append(listener)

        def unsubscribe() -> None:
            if listener in self._listeners:
                self._listeners.remove(listener)

        return unsubscribe

    def set_user_command(self, text: str) -> None:
        self.user_command = text.strip()
        self._notify()

    def set_omega_response(self, text: str) -> None:
        self.omega_response = text.strip()
        self._notify()

    def clear_conversation_display(self) -> None:
        self.user_command = ""
        self.omega_response = ""
        self._notify()

    def set_status(self, state: GuiState, *, demo_override: bool = False) -> bool:
        return self.state_manager.set_state(state, demo_override=demo_override)

    def start_listening_demo(self) -> None:
        self.set_status(GuiState.LISTENING)
        self.set_omega_response("Listening demonstration active. Microphone is off.")

    def sleep(self) -> None:
        self.clear_conversation_display()
        self.state_manager.reset()

    def emergency_stop(self) -> None:
        self.clear_conversation_display()
        self.state_manager.emergency_stop()
        self.set_omega_response(
            "Emergency stopped. Local demonstration activity has been cleared."
        )

    def close(self) -> None:
        self._unsubscribe_state()
        self._listeners.clear()

    def _state_changed(self, _state: GuiState, _metadata: GuiStateMetadata) -> None:
        self._notify()

    def _notify(self) -> None:
        snapshot = self.snapshot
        for listener in tuple(self._listeners):
            listener(snapshot)
