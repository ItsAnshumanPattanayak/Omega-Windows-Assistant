"""Deliberate confirmation and validated preference dialogs."""

from __future__ import annotations

import tkinter as tk
from collections.abc import Callable
from tkinter import messagebox, ttk

from omega.gui.models import ConfirmationRequest, GuiPreferences


class ConfirmationDialog:
    """Modal exact-scope confirmation that never approves on Enter or close."""

    def __init__(
        self,
        parent: tk.Tk | tk.Toplevel,
        request: ConfirmationRequest,
        on_confirm: Callable[[], None],
        on_cancel: Callable[[], None],
    ) -> None:
        self._on_confirm = on_confirm
        self._on_cancel = on_cancel
        self._resolved = False
        self.window = tk.Toplevel(parent)
        self.window.title("Omega confirmation required")
        self.window.transient(parent)
        self.window.resizable(False, False)
        self.window.protocol("WM_DELETE_WINDOW", self.cancel)
        self.window.bind("<Escape>", lambda _event: self.cancel())

        body = ttk.Frame(self.window, padding=18)
        body.grid(sticky="nsew")
        ttk.Label(
            body,
            text="Confirmation required",
            style="Header.TLabel",
        ).grid(row=0, column=0, columnspan=2, sticky="w")
        ttk.Label(
            body,
            text=request.prompt,
            justify="left",
            wraplength=480,
        ).grid(row=1, column=0, columnspan=2, sticky="w", pady=(12, 6))
        ttk.Label(
            body,
            text=f"Target: {request.display_target}",
            style="Muted.TLabel",
            wraplength=480,
        ).grid(row=2, column=0, columnspan=2, sticky="w")
        ttk.Label(
            body,
            text=f"Exact confirmation: {request.confirmation_phrase}",
            wraplength=480,
        ).grid(row=3, column=0, columnspan=2, sticky="w", pady=(8, 16))

        cancel = ttk.Button(body, text="Cancel", command=self.cancel)
        cancel.grid(row=4, column=0, sticky="e", padx=(0, 8))
        confirm = ttk.Button(
            body,
            text="Confirm deliberately",
            command=self.confirm,
        )
        confirm.grid(row=4, column=1, sticky="w")
        cancel.focus_set()
        self.window.grab_set()

    def confirm(self) -> None:
        if self._resolved:
            return
        self._resolved = True
        self.window.destroy()
        self._on_confirm()

    def cancel(self) -> None:
        if self._resolved:
            return
        self._resolved = True
        self.window.destroy()
        self._on_cancel()

    def dismiss(self) -> None:
        """Close because service state changed, without producing a new action."""

        self._resolved = True
        if self.window.winfo_exists():
            self.window.destroy()


class SettingsDialog:
    """Edit only the allowlisted mutable desktop preferences."""

    def __init__(
        self,
        parent: tk.Tk | tk.Toplevel,
        preferences: GuiPreferences,
        on_save: Callable[[GuiPreferences], None],
    ) -> None:
        self._on_save = on_save
        self._preferences = preferences
        self.window = tk.Toplevel(parent)
        self.window.title("Omega desktop settings")
        self.window.transient(parent)
        self.window.resizable(False, False)

        self.theme = tk.StringVar(value=preferences.theme)
        self.font_size = tk.StringVar(value=str(preferences.font_size))
        self.history_limit = tk.StringVar(value=str(preferences.history_limit))
        self.auto_scroll = tk.BooleanVar(value=preferences.auto_scroll)
        self.notifications = tk.BooleanVar(value=preferences.notifications_enabled)
        self.speak_responses = tk.BooleanVar(value=preferences.speak_responses)

        body = ttk.Frame(self.window, padding=18)
        body.grid(sticky="nsew")
        ttk.Label(body, text="Theme").grid(row=0, column=0, sticky="w", pady=4)
        ttk.Combobox(
            body,
            textvariable=self.theme,
            values=("system", "light", "dark"),
            state="readonly",
            width=18,
        ).grid(row=0, column=1, sticky="ew", pady=4)
        ttk.Label(body, text="Font size (9–24)").grid(
            row=1, column=0, sticky="w", pady=4
        )
        ttk.Entry(body, textvariable=self.font_size, width=20).grid(
            row=1, column=1, sticky="ew", pady=4
        )
        ttk.Label(body, text="History rows (1–100)").grid(
            row=2, column=0, sticky="w", pady=4
        )
        ttk.Entry(body, textvariable=self.history_limit, width=20).grid(
            row=2, column=1, sticky="ew", pady=4
        )
        ttk.Checkbutton(
            body,
            text="Automatically scroll conversation",
            variable=self.auto_scroll,
        ).grid(row=3, column=0, columnspan=2, sticky="w", pady=4)
        ttk.Checkbutton(
            body,
            text="Show in-application notifications",
            variable=self.notifications,
        ).grid(row=4, column=0, columnspan=2, sticky="w", pady=4)
        ttk.Checkbutton(
            body,
            text="Speak safe assistant responses when voice mode is running",
            variable=self.speak_responses,
        ).grid(row=5, column=0, columnspan=2, sticky="w", pady=4)
        ttk.Label(
            body,
            text=(
                "Safety, path, deletion, administrator, and confirmation "
                "settings are immutable here."
            ),
            style="Muted.TLabel",
            wraplength=420,
        ).grid(row=6, column=0, columnspan=2, sticky="w", pady=(10, 16))
        ttk.Button(body, text="Cancel", command=self.window.destroy).grid(
            row=7, column=0, sticky="e", padx=(0, 8)
        )
        ttk.Button(body, text="Save", command=self.save).grid(
            row=7, column=1, sticky="w"
        )

    def save(self) -> None:
        try:
            font_size = int(self.font_size.get())
            history_limit = int(self.history_limit.get())
        except ValueError:
            messagebox.showerror(
                "Invalid settings",
                "Font size and history rows must be whole numbers.",
                parent=self.window,
            )
            return
        if not 9 <= font_size <= 24 or not 1 <= history_limit <= 100:
            messagebox.showerror(
                "Invalid settings",
                "Font size must be 9–24 and history rows must be 1–100.",
                parent=self.window,
            )
            return
        current = GuiPreferences(
            theme=self.theme.get(),
            font_size=font_size,
            history_limit=history_limit,
            auto_scroll=self.auto_scroll.get(),
            notifications_enabled=self.notifications.get(),
            speak_responses=self.speak_responses.get(),
            window_width=self._preferences.window_width,
            window_height=self._preferences.window_height,
            maximized=self._preferences.maximized,
        )
        self.window.destroy()
        self._on_save(current)
