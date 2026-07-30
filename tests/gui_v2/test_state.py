from __future__ import annotations

import pytest

from omega.gui_v2 import (
    STATE_METADATA,
    GuiState,
    GuiStateManager,
    GuiStateTransitionError,
)


def test_all_required_states_have_accessible_metadata() -> None:
    expected = {
        "sleeping",
        "idle",
        "listening",
        "understanding",
        "planning",
        "waiting_for_confirmation",
        "executing",
        "speaking",
        "completed",
        "error",
        "permission_required",
        "emergency_stopped",
    }
    assert {state.value for state in GuiState} == expected
    assert set(STATE_METADATA) == set(GuiState)
    assert all(metadata.label for metadata in STATE_METADATA.values())
    assert all(metadata.description for metadata in STATE_METADATA.values())


def test_state_manager_notifies_valid_changes_and_repeats_are_idempotent() -> None:
    manager = GuiStateManager()
    changes: list[GuiState] = []
    unsubscribe = manager.subscribe(lambda state, _metadata: changes.append(state))

    assert manager.state is GuiState.SLEEPING
    assert manager.set_state(GuiState.IDLE)
    assert not manager.set_state(GuiState.IDLE)
    assert manager.set_state(GuiState.ERROR)
    unsubscribe()
    manager.reset()

    assert changes == [GuiState.IDLE, GuiState.ERROR]


def test_emergency_stop_requires_reset_before_continuing() -> None:
    manager = GuiStateManager(GuiState.EXECUTING)

    assert manager.emergency_stop()
    assert manager.state is GuiState.EMERGENCY_STOPPED
    with pytest.raises(GuiStateTransitionError, match="reset"):
        manager.set_state(GuiState.LISTENING)
    assert manager.reset()
    assert manager.set_state(GuiState.LISTENING)
