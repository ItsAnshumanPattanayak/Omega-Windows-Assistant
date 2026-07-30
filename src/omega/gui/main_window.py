"""Responsive ttk main window containing presentation logic only."""

from __future__ import annotations

import tkinter as tk
from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from tkinter import filedialog, messagebox, simpledialog, ttk
from typing import TYPE_CHECKING

from omega.gui.controller import GuiController, GuiView
from omega.gui.dialogs import ConfirmationDialog, SettingsDialog, about_text
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
from omega.voice.models import VoiceState

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
        self.command_input: tk.Text

        self.root.title(
            f"{application.settings.application_name} "
            f"{application.settings.application_version}"
        )
        self.root.minsize(800, 560)
        self.root.geometry(
            f"{self.preferences.window_width}x{self.preferences.window_height}"
        )
        self.root.protocol("WM_DELETE_WINDOW", self.close)

        runner = GuiTaskRunner(maximum_workers=2)
        self._runner = runner
        self.controller = GuiController(
            application.session,
            application.history_service,
            GuiPreferencesService(application.runtime_settings_repository),
            application.safety_gateway,
            runner,
            self,
            voice_factory=lambda sink: application.create_voice_service(
                event_sink=sink
            ),
            logger=get_logger("gui.controller"),
        )

        self._build()
        self.root.bind("<Control-l>", lambda _event: self.command_input.focus_set())
        self.root.bind("<F1>", lambda _event: self._help())
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
        essential_actions = (
            ("Activate", self._activate),
            ("Shutdown session", self._shutdown),
            ("Undo", self._undo),
            ("Settings", self._settings),
            ("Start voice", self._start_voice),
            ("Stop voice", self._stop_voice),
        )
        self.operation_buttons: list[ttk.Widget] = []
        for toolbar_index, (label, command) in enumerate(essential_actions):
            button = ttk.Button(toolbar, text=label, command=command)
            button.grid(row=0, column=toolbar_index, padx=2, pady=2, sticky="ew")
            self.operation_buttons.append(button)
            if label == "Undo":
                self.undo_button = button

        self.activity_actions = self._activity_action_groups()
        self.more_activities_menu = tk.Menu(self.root, tearoff=False)
        for category, actions in self.activity_actions.items():
            category_menu = tk.Menu(self.more_activities_menu, tearoff=False)
            for label, activity_command in actions:
                category_menu.add_command(label=label, command=activity_command)
            self.more_activities_menu.add_cascade(label=category, menu=category_menu)
        self.more_activities_button = ttk.Menubutton(
            toolbar,
            text="More Activities",
            menu=self.more_activities_menu,
        )
        self.more_activities_button.grid(
            row=0, column=len(essential_actions), padx=2, pady=2, sticky="ew"
        )
        self.activity_toggle_button = ttk.Button(
            toolbar, text="Hide activity", command=self._toggle_activity
        )
        self.activity_toggle_button.grid(
            row=0, column=len(essential_actions) + 1, padx=2, pady=2, sticky="ew"
        )
        self.operation_buttons.extend(
            [self.more_activities_button, self.activity_toggle_button]
        )
        for column in range(len(essential_actions) + 2):
            toolbar.columnconfigure(column, weight=1)

        panes = ttk.Panedwindow(self.root, orient=tk.HORIZONTAL)
        panes.grid(row=2, column=0, sticky="nsew", padx=12)
        self.panes = panes

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
        self.activity_frame = activity_frame
        self._activity_visible = True
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

        panes.add(conversation_frame, weight=5)
        panes.add(activity_frame, weight=1)

        status = ttk.Frame(self.root, padding=(12, 7))
        status.grid(row=3, column=0, sticky="ew")
        status.columnconfigure(1, weight=1)
        self.status_label = ttk.Label(status, text="Ready")
        self.status_label.grid(row=0, column=0, sticky="w")
        self.notification_label = ttk.Label(status, text="", style="Muted.TLabel")
        self.notification_label.grid(row=0, column=1, sticky="e")
        self.voice_label = ttk.Label(
            status,
            text="Voice: disabled",
            style="Muted.TLabel",
        )
        self.voice_label.grid(row=1, column=0, sticky="w", pady=(3, 0))
        self.transcription_label = ttk.Label(
            status,
            text="",
            style="Muted.TLabel",
        )
        self.transcription_label.grid(
            row=1,
            column=1,
            sticky="e",
            pady=(3, 0),
        )

    def _activity_action_groups(
        self,
    ) -> dict[str, tuple[tuple[str, Callable[[], object]], ...]]:
        """Return every secondary Version 1 action in stable categories."""

        return {
            "Applications and browser": (
                ("Open browser", self._open_browser),
                ("List tabs", self._list_tabs),
                ("Back", self._browser_back),
                ("Forward", self._browser_forward),
                ("Refresh page", self._browser_refresh),
            ),
            "Productivity": (
                ("Show history", self._show_history),
                ("Refresh activity", self._refresh),
                ("Undo", self._undo),
                ("Export history", self._export),
                ("Clear history", self._clear_history),
                ("Notes", self._list_notes),
                ("Tasks", self._list_tasks),
                ("Due today", self._due_tasks),
                ("Overdue", self._overdue_tasks),
            ),
            "Scheduling": (
                ("Reminders", self._list_reminders),
                ("Alarms", self._list_alarms),
                ("Timers", self._list_timers),
            ),
            "Knowledge": (
                ("Collections", self._knowledge_collections),
                ("Documents", self._knowledge_documents),
                ("Add document", self._add_knowledge_file),
                ("Add folder", self._add_knowledge_folder),
                ("Search", self._search_knowledge),
                ("Sources", self._knowledge_sources),
                ("Re-index source", self._reindex_knowledge_source),
                ("Remove source", self._remove_knowledge_source),
            ),
            "Email and calendar": (
                ("Email status", self._email_status),
                ("Inbox", self._list_emails),
                ("Unread email", self._list_unread_emails),
                ("Email search", self._search_emails),
                ("Open email", self._open_email),
                ("Summarize email", self._summarize_email),
                ("Draft email", self._draft_email),
                ("Reply draft", self._reply_email),
                ("Email drafts", self._list_email_drafts),
                ("Send draft", self._send_email_draft),
                ("Archive email", self._archive_email),
                ("Attachments", self._email_attachments),
                ("Calendar", self._calendar_today),
                ("Availability", self._calendar_availability),
                ("Calendar search", self._calendar_search),
                ("Add event", self._calendar_add),
            ),
            "Workflows": (
                ("List workflows", self.controller.list_workflows),
                ("New workflow", self._create_workflow),
                ("Preview workflow", self._preview_workflow),
            ),
            "Plugins and local AI": (
                ("Plugins", self.controller.list_plugins),
                ("Local AI status", self.controller.show_local_ai_status),
                ("AI models", self.controller.list_local_ai_models),
                ("Cancel AI", self.controller.cancel_ai_generation),
                ("Clear AI context", self.controller.clear_ai_conversation),
            ),
            "System and privacy": (
                ("Clipboard", self.controller.read_clipboard),
                ("Clear clipboard", self.controller.clear_clipboard),
                ("Screenshot", self.controller.capture_screenshot),
                ("Screenshots", self.controller.list_screenshots),
                ("Displays", self.controller.show_display_information),
                ("Windows", self.controller.list_visible_windows),
                ("My profile", self.controller.show_profile),
                ("Preferences", self.controller.show_preferences),
                ("Privacy settings", self.controller.show_privacy_preferences),
                ("Export profile", self.controller.export_profile),
                (
                    "Reset session preferences",
                    self.controller.reset_session_preferences,
                ),
                ("Help / About", self._help),
            ),
        }

    def _toggle_activity(self) -> None:
        """Show or hide the secondary activity pane without losing its data."""

        if self._activity_visible:
            self.panes.forget(self.activity_frame)
            self._activity_visible = False
            self.activity_toggle_button.configure(text="Show activity")
        else:
            self.panes.add(self.activity_frame, weight=1)
            self._activity_visible = True
            self.activity_toggle_button.configure(text="Hide activity")

    def _create_workflow(self) -> None:
        name = simpledialog.askstring(
            "New workflow", "Workflow name:", parent=self.root
        )
        if name and name.strip():
            self.controller.create_workflow(name.strip())

    def _preview_workflow(self) -> None:
        name = simpledialog.askstring(
            "Preview workflow", "Workflow name:", parent=self.root
        )
        if name and name.strip():
            self.controller.preview_workflow(name.strip())

    def add_message(self, message: ConversationMessage) -> None:
        self.conversation.configure(state="normal")
        kind = message.kind.value
        alignment = (
            "message_user" if message.kind is MessageKind.USER else "message_assistant"
        )
        timestamp = message.occurred_at.astimezone().strftime("%H:%M")
        self.conversation.insert(
            "end",
            f"{message.sender} · {timestamp}\n",
            (kind, alignment, "sender"),
        )
        self.conversation.insert(
            "end", message.text + "\n\n", (kind, alignment, "message_body")
        )
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
            button.configure({"state": "disabled" if busy else "normal"})
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
        font_size = max(
            9, min(48, round(preferences.font_size * preferences.font_scale))
        )
        theme = "high-contrast" if preferences.high_contrast else preferences.theme
        colors = self._theme.apply(theme, font_size)
        self.conversation.configure(
            background=colors["surface"],
            foreground=colors["foreground"],
            insertbackground=colors["foreground"],
            font=("Segoe UI", font_size),
        )
        self.command_input.configure(
            background=colors["surface"],
            foreground=colors["foreground"],
            insertbackground=colors["foreground"],
            font=("Segoe UI", font_size),
        )
        self.conversation.tag_configure("user", foreground=colors["accent"])
        self.conversation.tag_configure("assistant", foreground=colors["foreground"])
        self.conversation.tag_configure("system", foreground="#5f6368")
        self.conversation.tag_configure("success", foreground="#137333")
        self.conversation.tag_configure("warning", foreground="#b06000")
        self.conversation.tag_configure("error", foreground="#b3261e")
        self.conversation.tag_configure("sender", font=("Segoe UI Semibold", font_size))
        self.conversation.tag_configure(
            "message_user",
            justify="right",
            lmargin1=140,
            lmargin2=140,
            rmargin=14,
            spacing1=6,
            spacing3=4,
        )
        self.conversation.tag_configure(
            "message_assistant",
            justify="left",
            lmargin1=14,
            lmargin2=14,
            rmargin=140,
            spacing1=6,
            spacing3=4,
        )
        self.conversation.tag_configure("message_body", spacing2=2)
        self.root.geometry(f"{preferences.window_width}x{preferences.window_height}")
        if preferences.maximized:
            self.root.state("zoomed")

    def update_session_state(self, state: str) -> None:
        self.state_label.configure(text=state.upper())

    def update_voice_state(self, state: VoiceState, detail: str) -> None:
        self.voice_label.configure(
            text=f"Voice: {state.value.replace('_', ' ')} — {detail}"
        )

    def show_voice_transcription(self, transcript: str) -> None:
        preview = transcript if len(transcript) <= 80 else transcript[:79] + "…"
        self.transcription_label.configure(text=f'Heard: "{preview}"')

    def close(self) -> None:
        self._closing = True
        self.dismiss_confirmation()
        self.controller.close()
        self.application.shutdown()
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
            "About Omega Windows Assistant",
            about_text(self.application.session.activation_phrase),
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
        for item in self.application.notifications.drain():
            self.notify(
                Notification(
                    item.title,
                    item.message,
                    MessageKind.SYSTEM,
                )
            )
            self.add_message(
                ConversationMessage(
                    "Omega",
                    f"{item.schedule_type.value.title()}: {item.message}",
                    MessageKind.SYSTEM,
                    item.occurred_at,
                )
            )
        if not self._closing:
            self.root.after(25, self._poll_tasks)

    def _start_voice(self) -> None:
        self.controller.start_voice()

    def _stop_voice(self) -> None:
        self.controller.stop_voice()

    def _open_browser(self) -> None:
        self.controller.submit_command("open browser")

    def _list_tabs(self) -> None:
        self.controller.submit_command("list tabs")

    def _browser_back(self) -> None:
        self.controller.submit_command("go back")

    def _browser_forward(self) -> None:
        self.controller.submit_command("go forward")

    def _browser_refresh(self) -> None:
        self.controller.submit_command("refresh page")

    def _list_reminders(self) -> None:
        self.controller.submit_command("list reminders")

    def _list_alarms(self) -> None:
        self.controller.submit_command("list alarms")

    def _list_timers(self) -> None:
        self.controller.submit_command("list timers")

    def _list_notes(self) -> None:
        self.controller.submit_command("list notes")

    def _list_tasks(self) -> None:
        self.controller.submit_command("list tasks")

    def _due_tasks(self) -> None:
        self.controller.submit_command("show tasks due today")

    def _overdue_tasks(self) -> None:
        self.controller.submit_command("show overdue tasks")

    def _knowledge_collections(self) -> None:
        self.controller.submit_command("show my knowledge collections")

    def _knowledge_documents(self) -> None:
        self.controller.submit_command("list my knowledge documents")

    def _add_knowledge_file(self) -> None:
        path = filedialog.askopenfilename(
            parent=self.root,
            title="Add a local knowledge document",
            filetypes=(
                ("Supported documents", "*.pdf *.docx *.txt *.md *.markdown"),
                ("All files", "*.*"),
            ),
        )
        if path:
            self.controller.add_knowledge_file(path)

    def _add_knowledge_folder(self) -> None:
        path = filedialog.askdirectory(
            parent=self.root,
            title="Add a local knowledge folder (non-recursive)",
            mustexist=True,
        )
        if path:
            self.controller.add_knowledge_directory(path)

    def _search_knowledge(self) -> None:
        query = simpledialog.askstring(
            "Search local knowledge",
            "Search for:",
            parent=self.root,
        )
        if query and query.strip():
            self.controller.search_knowledge(query.strip())

    def _knowledge_sources(self) -> None:
        self.controller.list_knowledge_sources()

    def _reindex_knowledge_source(self) -> None:
        reference = simpledialog.askstring(
            "Re-index local source",
            "Document title, filename, or source ID:",
            parent=self.root,
        )
        if reference and reference.strip():
            self.controller.reindex_knowledge_source(reference.strip())

    def _remove_knowledge_source(self) -> None:
        reference = simpledialog.askstring(
            "Remove local source",
            "Document title, filename, or source ID:",
            parent=self.root,
        )
        if reference and reference.strip():
            self.controller.remove_knowledge_source(reference.strip())

    def _email_status(self) -> None:
        self.controller.email_status()

    def _list_emails(self) -> None:
        self.controller.list_emails()

    def _list_unread_emails(self) -> None:
        self.controller.list_emails(unread_only=True)

    def _search_emails(self) -> None:
        query = simpledialog.askstring("Search email", "Search for:", parent=self.root)
        if query and query.strip():
            self.controller.search_emails(query.strip())

    def _open_email(self) -> None:
        number = simpledialog.askinteger(
            "Open email", "Email number:", parent=self.root, minvalue=1
        )
        if number is not None:
            self.controller.open_email(number)

    def _summarize_email(self) -> None:
        self.controller.summarize_email()

    def _draft_email(self) -> None:
        recipient = simpledialog.askstring(
            "Draft email", "Recipient address:", parent=self.root
        )
        if not recipient or not recipient.strip():
            return
        subject = (
            simpledialog.askstring(
                "Draft email", "Subject (optional):", parent=self.root
            )
            or ""
        )
        self.controller.create_email_draft(recipient.strip(), subject.strip())

    def _reply_email(self) -> None:
        self.controller.reply_to_email()

    def _list_email_drafts(self) -> None:
        self.controller.list_email_drafts()

    def _send_email_draft(self) -> None:
        self.controller.send_email_draft()

    def _archive_email(self) -> None:
        self.controller.archive_email()

    def _email_attachments(self) -> None:
        self.controller.show_email_attachments()

    def _calendar_today(self) -> None:
        self.controller.list_calendar_events("today")

    def _calendar_availability(self) -> None:
        self.controller.calendar_availability("today")

    def _calendar_search(self) -> None:
        query = simpledialog.askstring(
            "Search calendar", "Search for:", parent=self.root
        )
        if query and query.strip():
            self.controller.search_calendar(query.strip())

    def _calendar_add(self) -> None:
        title = simpledialog.askstring("Add calendar event", "Title:", parent=self.root)
        if not title or not title.strip():
            return
        day = simpledialog.askstring(
            "Add calendar event",
            "Day (today, tomorrow, or YYYY-MM-DD):",
            parent=self.root,
        )
        if not day or not day.strip():
            return
        clock = simpledialog.askstring(
            "Add calendar event", "Time (for example 4 pm or 16:00):", parent=self.root
        )
        if clock and clock.strip():
            self.controller.create_calendar_event(
                title.strip(), day.strip(), clock.strip()
            )
