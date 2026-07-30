from omega.gui_v2 import GuiState, GuiStateManager, OmegaV2ViewModel


def test_public_display_methods_and_emergency_stop() -> None:
    model = OmegaV2ViewModel(GuiStateManager())
    snapshots = []
    model.subscribe(snapshots.append)

    model.set_user_command(" Open YouTube ")
    model.set_omega_response(" Opening YouTube. ")
    assert model.snapshot.user_command == "Open YouTube"
    assert model.snapshot.omega_response == "Opening YouTube."

    model.start_listening_demo()
    assert model.snapshot.state is GuiState.LISTENING
    assert "Microphone is off" in model.snapshot.omega_response

    model.emergency_stop()
    assert model.snapshot.state is GuiState.EMERGENCY_STOPPED
    assert model.snapshot.user_command == ""
    assert "Emergency stopped" in model.snapshot.omega_response
    assert snapshots


def test_sleep_clears_demo_state() -> None:
    model = OmegaV2ViewModel(GuiStateManager(GuiState.IDLE))
    model.set_user_command("demo")
    model.sleep()
    assert model.snapshot.state is GuiState.SLEEPING
    assert model.snapshot.user_command == ""
