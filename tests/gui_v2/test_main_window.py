from __future__ import annotations

import tkinter as tk

import pytest

from omega.gui_v2 import GuiState, V2GuiConfiguration
from omega.gui_v2.main_window import OmegaV2MainWindow


def test_main_window_smoke_and_public_updates() -> None:
    try:
        root = tk.Tk()
    except tk.TclError as error:
        pytest.skip(f"Tk window unavailable on this host: {error}")
    root.withdraw()
    window = OmegaV2MainWindow(root, V2GuiConfiguration(animation_enabled=False))

    assert window.status_label.winfo_exists()
    assert window.command_label.winfo_exists()
    assert window.response_label.winfo_exists()
    assert window.emergency_button.winfo_exists()
    window.set_user_command("Open YouTube")
    window.set_omega_response("Opening YouTube.")
    window.set_status(GuiState.IDLE)
    root.update_idletasks()
    assert "Open YouTube" in window.command_label.cget("text")
    assert "Opening YouTube" in window.response_label.cget("text")
    assert window.status_label.cget("text") == "IDLE"

    window.view_model.emergency_stop()
    root.update_idletasks()
    assert window.status_label.cget("text") == "EMERGENCY STOPPED"
    window.close()
