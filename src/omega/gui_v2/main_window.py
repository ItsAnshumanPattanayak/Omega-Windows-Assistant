"""Modern Tk presentation shell for the Omega V2 Phase 1 foundation."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Any

from omega.gui_v2.assets import resolve_gui_asset
from omega.gui_v2.configuration import V2GuiConfiguration
from omega.gui_v2.state import GuiState, GuiStateManager
from omega.gui_v2.video import SilentLoopingVideoController
from omega.gui_v2.view_model import OmegaV2ViewModel, V2ViewSnapshot


class OmegaV2MainWindow:
    """Compose widgets while delegating state and video behavior to controllers."""

    def __init__(
        self,
        root: tk.Tk,
        configuration: V2GuiConfiguration | None = None,
        *,
        state_manager: GuiStateManager | None = None,
        video_controller: SilentLoopingVideoController | None = None,
    ) -> None:
        self.root = root
        self.configuration = configuration or V2GuiConfiguration()
        self.state_manager = state_manager or GuiStateManager(
            self.configuration.default_state
        )
        self.view_model = OmegaV2ViewModel(self.state_manager)
        video_path = resolve_gui_asset(self.configuration.video_asset_relative_path)
        self.video_controller = video_controller or SilentLoopingVideoController(
            video_path, loop=self.configuration.video_loop
        )
        self._after_identifier: str | None = None
        self._photo: Any | None = None
        self._closing = False
        self._unsubscribe = self.view_model.subscribe(self._render_snapshot)

        self.root.title(self.configuration.window_title)
        self.root.minsize(
            self.configuration.minimum_width, self.configuration.minimum_height
        )
        if self.configuration.fullscreen:
            self.root.attributes("-fullscreen", True)
        self.root.configure(background="#070b14")
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self._configure_styles()
        self._build()
        self._render_snapshot(self.view_model.snapshot)
        self._start_animation()

    def _configure_styles(self) -> None:
        style = ttk.Style(self.root)
        style.theme_use("clam")
        style.configure("V2.TFrame", background="#070b14")
        style.configure("Panel.V2.TFrame", background="#101827")
        style.configure(
            "Title.V2.TLabel",
            background="#070b14",
            foreground="#d9f8ff",
            font=("Segoe UI Semibold", 22),
        )
        style.configure(
            "Status.V2.TLabel",
            background="#070b14",
            foreground="#58d8ff",
            font=("Segoe UI Semibold", 12),
        )
        style.configure(
            "Body.V2.TLabel",
            background="#101827",
            foreground="#e8f3ff",
            font=("Segoe UI", 11),
        )
        style.configure(
            "Muted.V2.TLabel",
            background="#070b14",
            foreground="#9db0c7",
            font=("Segoe UI", 10),
        )
        style.configure("V2.TButton", padding=(12, 8))
        style.configure("Emergency.V2.TButton", padding=(14, 8))

    def _build(self) -> None:
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(2, weight=1)

        header = ttk.Frame(self.root, style="V2.TFrame", padding=(22, 16, 22, 8))
        header.grid(row=0, column=0, sticky="ew")
        header.columnconfigure(0, weight=1)
        ttk.Label(header, text="OMEGA", style="Title.V2.TLabel").grid(
            row=0, column=0, sticky="w"
        )
        self.status_label = ttk.Label(header, style="Status.V2.TLabel")
        self.status_label.grid(row=0, column=1, sticky="e")
        self.status_support = ttk.Label(header, style="Muted.V2.TLabel", anchor="e")
        self.status_support.grid(
            row=1, column=0, columnspan=2, sticky="ew", pady=(4, 0)
        )

        conversation = ttk.Frame(self.root, style="Panel.V2.TFrame", padding=(18, 12))
        conversation.grid(row=1, column=0, sticky="ew", padx=22, pady=(4, 10))
        conversation.columnconfigure(0, weight=1)
        self.command_label = ttk.Label(
            conversation,
            text="You said: —",
            style="Body.V2.TLabel",
            anchor="w",
        )
        self.command_label.grid(row=0, column=0, sticky="ew")
        self.response_label = ttk.Label(
            conversation,
            text="Omega: —",
            style="Body.V2.TLabel",
            anchor="w",
        )
        self.response_label.grid(row=1, column=0, sticky="ew", pady=(8, 0))

        self.video_panel = tk.Label(
            self.root,
            text="Preparing silent Omega animation…",
            background="#05070d",
            foreground="#8ddfff",
            font=("Segoe UI", 12),
            anchor="center",
            takefocus=True,
            highlightthickness=1,
            highlightbackground="#183248",
        )
        self.video_panel.grid(row=2, column=0, sticky="nsew", padx=22, pady=(0, 12))

        controls = ttk.Frame(self.root, style="V2.TFrame", padding=(22, 0, 22, 18))
        controls.grid(row=3, column=0, sticky="ew")
        controls.columnconfigure(2, weight=1)
        self.listen_button = ttk.Button(
            controls,
            text="Start listening demo",
            command=self.view_model.start_listening_demo,
            style="V2.TButton",
            takefocus=True,
        )
        self.listen_button.grid(row=0, column=0, padx=(0, 8))
        self.sleep_button = ttk.Button(
            controls,
            text="Sleep",
            command=self.view_model.sleep,
            style="V2.TButton",
            takefocus=True,
        )
        self.sleep_button.grid(row=0, column=1)
        self.emergency_button = ttk.Button(
            controls,
            text="Emergency stop",
            command=self.view_model.emergency_stop,
            style="Emergency.V2.TButton",
            takefocus=True,
        )
        self.emergency_button.grid(row=0, column=3, sticky="e")
        if self.configuration.demo_mode:
            self._build_demo_control(controls)

    def _build_demo_control(self, parent: ttk.Frame) -> None:
        self.demo_state = tk.StringVar(value=self.state_manager.state.value)
        selector = ttk.Combobox(
            parent,
            textvariable=self.demo_state,
            values=tuple(state.value for state in GuiState),
            state="readonly",
            width=28,
            takefocus=True,
        )
        selector.grid(row=0, column=2, padx=12)
        selector.bind(
            "<<ComboboxSelected>>",
            lambda _event: self.set_status(
                GuiState(self.demo_state.get()), demo_override=True
            ),
        )

    def set_user_command(self, text: str) -> None:
        self.view_model.set_user_command(text)

    def set_omega_response(self, text: str) -> None:
        self.view_model.set_omega_response(text)

    def clear_conversation_display(self) -> None:
        self.view_model.clear_conversation_display()

    def set_status(self, state: GuiState, *, demo_override: bool = False) -> bool:
        return self.view_model.set_status(state, demo_override=demo_override)

    def _render_snapshot(self, snapshot: V2ViewSnapshot) -> None:
        self.status_label.configure(text=snapshot.metadata.label.upper())
        self.status_support.configure(text=snapshot.metadata.description)
        self.command_label.configure(text=f"You said: {snapshot.user_command or '—'}")
        self.response_label.configure(text=f"Omega: {snapshot.omega_response or '—'}")
        intensity = max(0.0, min(1.0, snapshot.metadata.visual_intensity))
        blue = 72 + round(183 * intensity)
        self.video_panel.configure(highlightbackground=f"#1850{blue:02x}")
        listen_enabled = snapshot.state in {
            GuiState.SLEEPING,
            GuiState.IDLE,
            GuiState.COMPLETED,
            GuiState.ERROR,
        }
        self.listen_button.configure(state="normal" if listen_enabled else "disabled")
        self.emergency_button.configure(
            state=(
                "disabled" if snapshot.state is GuiState.EMERGENCY_STOPPED else "normal"
            )
        )

    def _start_animation(self) -> None:
        if not self.configuration.animation_enabled:
            self._show_animation_fallback("Animation is disabled.")
            return
        if not self.video_controller.open():
            self._show_animation_fallback(self.video_controller.failure_reason)
            return
        self._render_next_frame()

    def _render_next_frame(self) -> None:
        self._after_identifier = None
        if self._closing:
            return
        frame = self.video_controller.next_frame()
        if frame is None:
            self._show_animation_fallback(self.video_controller.failure_reason)
            return
        try:
            from PIL import Image, ImageOps, ImageTk

            rgb_frame = frame[:, :, ::-1].copy()
            image = Image.fromarray(rgb_frame)
            width = max(1, self.video_panel.winfo_width())
            height = max(1, self.video_panel.winfo_height())
            image = ImageOps.contain(image, (width, height), Image.Resampling.LANCZOS)
            self._photo = ImageTk.PhotoImage(image)
            self.video_panel.configure(image=self._photo, text="")
        except Exception:
            self._show_animation_fallback("Animation rendering is unavailable.")
            return
        self._after_identifier = self.root.after(
            self.video_controller.frame_interval_ms, self._render_next_frame
        )

    def _show_animation_fallback(self, reason: str) -> None:
        self.video_controller.close()
        self.video_panel.configure(
            image="", text=f"OMEGA\n\n{reason or 'Static visual mode is active.'}"
        )

    def close(self) -> None:
        if self._closing:
            return
        self._closing = True
        if self._after_identifier is not None:
            self.root.after_cancel(self._after_identifier)
            self._after_identifier = None
        self.video_controller.close()
        self._unsubscribe()
        self.view_model.close()
        self.root.destroy()
