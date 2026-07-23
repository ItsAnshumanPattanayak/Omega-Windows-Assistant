"""Responsive ttk main window containing presentation logic only."""

from __future__ import annotations

import tkinter as tk
from collections.abc import Sequence
from datetime import UTC, datetime
from tkinter import messagebox, ttk
from typing import TYPE_CHECKING

from omega.gui.controller import GuiController, GuiView
from omega.gui.dialogs import ConfirmationDialog, SettingsDialog
from omega.gui.models import (
    ActivityItem,
    ConfirmationRequest,
    ConversationMessage,
    GuiPreferences,
    GuiStatus,
    MessageKind,
    Notification,
    UndoAvailability,
)
from omega.gui.preferences import GuiPreferencesService
from omega.gui.task_runner import GuiTaskRunner
from omega.gui.theme import ThemeManager
from omega.utils.logger import get_logger

if TYPE_CHECKING:
    from omega.app import OmegaApplication


class OmegaMainWindow(GuiView):
    """Compose widgets and forward all operations to ``GuiController``."""

    def __init__(self, root: tk.Tk, application: OmegaApplication) -> None:
        self.root = root
        self.application = application
        self.preferences = GuiPreferences()
        self._confirmation: ConfirmationDialog | None = None
        self._undo_available = False
        self._closing = False
        self._theme = ThemeManager(root)

        self.root.title(
            f"{application.settings.application_name} "
            f"{application.settings.application_version}"
        )
        self.root.minsize(760, 520)
        self.root.geometry(
            f"{self.preferences.window_width}x{self.preferences.window_height}"
        )
        self.root.protocol("WM_DELETE_WINDOW", self.close)

        self._build()
        runner = GuiTaskRunner(maximum_workers=2)
        self._runner = runner
        self.controller = GuiController(
            application.session,
            application.history_service,
            GuiPreferencesService(application.runtime_settings_repository),
            application.safety_gateway,
            runner,
            self,
            logger=get_logger("gui.controller"),
        )
        self.apply_preferences(self.preferences)
        self.add_message(
            ConversationMessage(
                "System",
                (
                    "Omega desktop is ready. Activate Omega before submitting "
                    "assistant commands."
                ),
                MessageKind.SYSTEM,
                datetime.now(UTC),
            )
        )
        self.controller.start()
        self.root.after(25, self._poll_tasks)

    def _build(self) -> None:
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(2, weight=1)

        header = ttk.Frame(self.root, padding=(16, 12))
        header.grid(row=0, column=0, sticky="ew")
        header.columnconfigure(1, weight=1)
        ttk.Label(header, text="Omega", style="Header.TLabel").grid(
            row=0, column=0, sticky="w"
        )
        self.state_label = ttk.Label(header, text="INACTIVE", style="State.TLabel")
        self.state_label.grid(row=0, column=1, sticky="e")

        toolbar = ttk.Frame(self.root, padding=(12, 0, 12, 8))
        toolbar.grid(row=1, column=0, sticky="ew")
        actions = (
            ("Activate", self._activate),
            ("Shutdown session", self._shutdown),
            ("Show history", self._show_history),
            ("Refresh", self._refresh),
            ("Undo", self._undo),
            ("Export", self._export),
            ("Clear history", self._clear_history),
            ("Settings", self._settings),
            ("Help / About", self._help),
        )
        self.operation_buttons: list[ttk.Button] = []
        for toolbar_index, (label, command) in enumerate(actions):
            button = ttk.Button(toolbar, text=label, command=command)
            button.grid(
                row=toolbar_index // 5,
                column=toolbar_index % 5,
                padx=2,
                pady=2,
                sticky="ew",
            )
            self.operation_buttons.append(button)
            if label == "Undo":
                self.undo_button = button

        panes = ttk.Panedwindow(self.root, orient=tk.HORIZONTAL)
        panes.grid(row=2, column=0, sticky="nsew", padx=12)

        conversation_frame = ttk.Frame(panes, padding=8)
        conversation_frame.columnconfigure(0, weight=1)
        conversation_frame.rowconfigure(1, weight=1)
        ttk.Label(conversation_frame, text="Conversation").grid(
            row=0, column=0, sticky="w", pady=(0, 6)
        )
        self.conversation = tk.Text(
            conversation_frame,
            wrap="word",
            state="disabled",
            undo=False,
            padx=10,
            pady=10,
        )
        conversation_scroll = ttk.Scrollbar(
            conversation_frame,
            orient="vertical",
            command=self.conversation.yview,
        )
        self.conversation.configure(yscrollcommand=conversation_scroll.set)
        self.conversation.grid(row=1, column=0, sticky="nsew")
        conversation_scroll.grid(row=1, column=1, sticky="ns")

        input_frame = ttk.Frame(conversation_frame)
        input_frame.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(8, 0))
        input_frame.columnconfigure(0, weight=1)
        self.command_input = tk.Text(input_frame, height=3, wrap="word", undo=True)
        self.command_input.grid(row=0, column=0, sticky="ew")
        self.command_input.bind("<Return>", self._enter)
        self.send_button = ttk.Button(input_frame, text="Send", command=self._send)
        self.send_button.grid(row=0, column=1, sticky="ns", padx=(8, 0))

        activity_frame = ttk.Frame(panes, padding=8)
        activity_frame.columnconfigure(0, weight=1)
        activity_frame.rowconfigure(1, weight=1)
        ttk.Label(activity_frame, text="Recent activity").grid(
            row=0, column=0, sticky="w", pady=(0, 6)
        )
        self.activity = ttk.Treeview(
            activity_frame,
            columns=("time", "kind", "summary", "status"),
            show="headings",
            selectmode="browse",
        )
        columns: tuple[tuple[str, str, int], ...] = (
            ("time", "Time", 135),
            ("kind", "Kind", 75),
            ("summary", "Summary", 250),
            ("status", "Status", 90),
        )
        for activity_column, heading, width in columns:
            self.activity.heading(activity_column, text=heading)
            self.activity.column(activity_column, width=width, minwidth=60)
        activity_scroll = ttk.Scrollbar(
            activity_frame, orient="vertical", command=self.activity.yview
        )
        self.activity.configure(yscrollcommand=activity_scroll.set)
        self.activity.grid(row=1, column=0, sticky="nsew")
        activity_scroll.grid(row=1, column=1, sticky="ns")

        panes.add(conversation_frame, weight=3)
        panes.add(activity_frame, weight=2)

        status = ttk.Frame(self.root, padding=(12, 7))
        status.grid(row=3, column=0, sticky="ew")
        status.columnconfigure(1, weight=1)
        self.status_label = ttk.Label(status, text="Ready")
        self.status_label.grid(row=0, column=0, sticky="w")
        self.notification_label = ttk.Label(status, text="", style="Muted.TLabel")
        self.notification_label.grid(row=0, column=1, sticky="e")

    def add_message(self, message: ConversationMessage) -> None:
        self.conversation.configure(state="normal")
        tag = message.kind.value
        self.conversation.insert("end", f"{message.sender}: ", (tag, "sender"))
        self.conversation.insert("end", message.text + "\n\n", (tag,))
        self.conversation.configure(state="disabled")
        if self.preferences.auto_scroll:
            self.conversation.see("end")

    def set_status(self, status: GuiStatus, detail: str) -> None:
        label = status.value.replace("_", " ").title()
        self.status_label.configure(text=f"{label}: {detail}")

    def set_busy(self, busy: bool) -> None:
        if busy:
            self.send_button.configure(state="disabled")
            self.command_input.configure(state="disabled")
        else:
            self.send_button.configure(state="normal")
            self.command_input.configure(state="normal")
        for button in self.operation_buttons:
            button.configure(state="disabled" if busy else "normal")
        if not busy and not self._undo_available:
            self.undo_button.configure(state="disabled")

    def show_activity(self, items: Sequence[ActivityItem]) -> None:
        for item_id in self.activity.get_children():
            self.activity.delete(item_id)
        if not items:
            self.activity.insert("", "end", values=("", "", "No activity yet.", ""))
            return
        for item in items:
            self.activity.insert(
                "",
                "end",
                iid=item.identifier,
                values=(item.timestamp, item.kind, item.summary, item.status),
            )

    def set_undo_availability(self, availability: UndoAvailability) -> None:
        self._undo_available = availability.available
        self.undo_button.configure(
            text=(
                f"Undo: {availability.description}"
                if availability.available
                else "Undo"
            ),
            state=(
                "normal"
                if availability.available and not self.controller.busy
                else "disabled"
            ),
        )

    def show_confirmation(self, request: ConfirmationRequest) -> None:
        self.dismiss_confirmation()
        self._confirmation = ConfirmationDialog(
            self.root,
            request,
            self._confirm_pending,
            self._cancel_pending,
        )

    def dismiss_confirmation(self) -> None:
        if self._confirmation is not None:
            self._confirmation.dismiss()
            self._confirmation = None

    def notify(self, notification: Notification) -> None:
        self.notification_label.configure(
            text=f"{notification.title}: {notification.message}"
        )
        self.root.after(6000, self._clear_notification)

    def apply_preferences(self, preferences: GuiPreferences) -> None:
        self.preferences = preferences
        colors = self._theme.apply(preferences.theme, preferences.font_size)
        self.conversation.configure(
            background=colors["surface"],
            foreground=colors["foreground"],
            insertbackground=colors["foreground"],
            font=("Segoe UI", preferences.font_size),
        )
        self.command_input.configure(
            background=colors["surface"],
            foreground=colors["foreground"],
            insertbackground=colors["foreground"],
            font=("Segoe UI", preferences.font_size),
        )
        self.conversation.tag_configure("user", foreground=colors["accent"])
        self.conversation.tag_configure("assistant", foreground=colors["foreground"])
        self.conversation.tag_configure("system", foreground="#5f6368")
        self.conversation.tag_configure("success", foreground="#137333")
        self.conversation.tag_configure("warning", foreground="#b06000")
        self.conversation.tag_configure("error", foreground="#b3261e")
        self.conversation.tag_configure(
            "sender", font=("Segoe UI Semibold", preferences.font_size)
        )
        self.root.geometry(f"{preferences.window_width}x{preferences.window_height}")
        if preferences.maximized:
            self.root.state("zoomed")

    def update_session_state(self, state: str) -> None:
        self.state_label.configure(text=state.upper())

    def close(self) -> None:
        self._closing = True
        self.dismiss_confirmation()
        self.controller.close()
        self.root.destroy()

    def _send(self) -> None:
        text = self.command_input.get("1.0", "end-1c")
        if self.controller.submit_command(text):
            self.command_input.delete("1.0", "end")

    def _enter(self, event: tk.Event[tk.Misc]) -> str | None:
        if int(event.state) & 0x0001:
            return None
        self._send()
        return "break"

    def _activate(self) -> None:
        self.controller.activate()

    def _shutdown(self) -> None:
        self.controller.shutdown_session()

    def _show_history(self) -> None:
        self.controller.show_history()

    def _refresh(self) -> None:
        self.controller.refresh_activity()

    def _undo(self) -> None:
        self.controller.request_undo()

    def _export(self) -> None:
        self.controller.export_history()

    def _clear_history(self) -> None:
        self.controller.clear_history()

    def _settings(self) -> None:
        SettingsDialog(
            self.root,
            self.controller.current_preferences,
            self._save_preferences,
        )

    def _help(self) -> None:
        messagebox.showinfo(
            "About Omega",
            (
                "Omega is a safety-first Windows assistant.\n\n"
                f'Activate with "{self.application.session.activation_phrase}".\n'
                "Commands and confirmations use the same production session "
                "and safety gateway as terminal mode.\n\n"
                "Voice and browser automation are not available."
            ),
            parent=self.root,
        )

    def _clear_notification(self) -> None:
        if self.notification_label.winfo_exists():
            self.notification_label.configure(text="")

    def _confirm_pending(self) -> None:
        self.controller.confirm_pending()

    def _cancel_pending(self) -> None:
        self.controller.cancel_pending()

    def _save_preferences(self, preferences: GuiPreferences) -> None:
        self.controller.save_preferences(preferences)

    def _poll_tasks(self) -> None:
        self._runner.drain_callbacks()
        if not self._closing:
            self.root.after(25, self._poll_tasks)
