"""Privacy-redacted dispatch for explicit desktop utility commands."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from hashlib import sha256
from uuid import UUID

from omega.desktop_utilities import (
    ClipboardService,
    DesktopInformationService,
    DesktopUtilityError,
    ScreenshotRegion,
    ScreenshotRequest,
    ScreenshotService,
    ScreenshotTarget,
)
from omega.models import (
    Action,
    ActionResult,
    ConfirmationStatus,
    ErrorCategory,
    IntentType,
    OmegaErrorDetails,
    PermissionDecision,
    RiskLevel,
    UserCommand,
)
from omega.safety import (
    ConfirmationSpec,
    ResourceFingerprint,
    SafeExecutionGateway,
    SafetyContext,
)
from omega.understanding.result import CommandParseResult

_INTENTS = frozenset(
    {
        IntentType.COPY_TEXT_TO_CLIPBOARD,
        IntentType.READ_CLIPBOARD,
        IntentType.CLEAR_CLIPBOARD,
        IntentType.SEARCH_CLIPBOARD,
        IntentType.SAVE_CLIPBOARD_TO_FILE,
        IntentType.CLIPBOARD_TO_NOTE,
        IntentType.CAPTURE_SCREENSHOT,
        IntentType.LIST_SCREENSHOTS,
        IntentType.OPEN_SCREENSHOT,
        IntentType.DELETE_SCREENSHOT,
        IntentType.SHOW_DISPLAY_INFORMATION,
        IntentType.SHOW_ACTIVE_WINDOW,
        IntentType.LIST_VISIBLE_WINDOWS,
        IntentType.FIND_WINDOW,
        IntentType.BRING_WINDOW_TO_FRONT,
    }
)
_DESTRUCTIVE = {IntentType.CLEAR_CLIPBOARD, IntentType.DELETE_SCREENSHOT}


@dataclass(frozen=True)
class DesktopUtilityDispatchResult:
    command: UserCommand
    action: Action
    result: ActionResult

    @property
    def user_message(self) -> str:
        return self.result.user_message


class DesktopUtilityActionDispatcher:
    """Route bounded operations through the centralized safety gateway."""

    def __init__(
        self,
        clipboard: ClipboardService,
        screenshots: ScreenshotService,
        information: DesktopInformationService,
        gateway: SafeExecutionGateway,
        *,
        save_text: Callable[[str, str, UUID], str] | None = None,
        create_note: Callable[[str, str, UUID], str] | None = None,
    ) -> None:
        self.clipboard, self.screenshots, self.information = (
            clipboard,
            screenshots,
            information,
        )
        self.gateway, self.save_text, self.create_note = gateway, save_text, create_note

    def dispatch(
        self, parsed: CommandParseResult
    ) -> DesktopUtilityDispatchResult | None:
        original = parsed.command
        if (
            not parsed.matched
            or parsed.requires_clarification
            or original.intent not in _INTENTS
        ):
            return None
        command = self._redacted(original)
        destructive = command.intent in _DESTRUCTIVE
        action = Action(
            command.command_id,
            command.intent,
            parameters={
                "desktop_operation": command.intent.value,
                "content_persisted": False,
            },
            risk_level=RiskLevel.HIGH if destructive else RiskLevel.MEDIUM,
            permission_decision=PermissionDecision.ALLOW,
            confirmation_status=ConfirmationStatus.NOT_REQUIRED,
            requires_confirmation=False,
        )
        confirmation, fingerprint, revalidator = (
            self._prepare(original) if destructive else (None, None, None)
        )
        context = SafetyContext(
            command,
            action,
            original.session_id or UUID(int=0),
            logical_source=command.intent.value,
            target_type="desktop_utility",
            target_exists=True,
            additional_context={"shell_like": False, "bulk_operation": False},
        )

        def executor() -> ActionResult:
            return self._execute(original, action)

        if confirmation is None or fingerprint is None or revalidator is None:
            value = self.gateway.submit(context, executor)
        else:
            value = self.gateway.submit(
                context,
                executor,
                confirmation=confirmation,
                fingerprint=fingerprint,
                revalidator=revalidator,
            )
        return DesktopUtilityDispatchResult(value.command, value.action, value.result)

    def clear_session(self) -> None:
        self.screenshots.clear_session()
        self.information.clear_session()

    def _prepare(self, command: UserCommand) -> tuple[
        ConfirmationSpec,
        ResourceFingerprint,
        Callable[[], ResourceFingerprint | None],
    ]:
        if command.intent is IntentType.CLEAR_CLIPBOARD:
            fingerprint = self._clipboard_fingerprint()
            return (
                ConfirmationSpec(
                    "clipboard",
                    'Clear the current clipboard text? Type "confirm clear clipboard".',
                    "confirm clear clipboard",
                    "cancel clear clipboard",
                ),
                fingerprint,
                self._clipboard_fingerprint,
            )
        reference = self._number(command, "screenshot_reference")
        record = self.screenshots.select(reference)
        phrase = f"confirm delete screenshot {record.screenshot_id}"
        return (
            ConfirmationSpec(
                record.screenshot_id,
                f"Delete {record.path.name} through the recovery path? "
                f'Type "{phrase}".',
                phrase,
                f"cancel delete screenshot {record.screenshot_id}",
            ),
            SafeExecutionGateway.fingerprint_path(record.path),
            lambda: SafeExecutionGateway.fingerprint_path(record.path),
        )

    def _clipboard_fingerprint(self) -> ResourceFingerprint:
        digest = sha256(self.clipboard.read().encode("utf-8")).hexdigest()
        return ResourceFingerprint("clipboard_text", digest, True)

    def _execute(self, command: UserCommand, action: Action) -> ActionResult:
        try:
            message = self._run(command)
            return ActionResult.success_result(
                action.action_id, "Desktop utility completed.", message
            )
        except (DesktopUtilityError, OSError) as error:
            safe = str(error) or "The desktop utility could not be completed safely."
            details = OmegaErrorDetails(
                "DESKTOP_UTILITY_FAILED",
                ErrorCategory.EXECUTION,
                "Desktop utility failed safely.",
                safe,
                True,
                details={"sensitive_details_omitted": True},
                action_id=action.action_id,
                command_id=command.command_id,
            )
            return ActionResult.failure_result(
                action.action_id, "Desktop utility failed safely.", safe, details
            )

    def _run(self, command: UserCommand) -> str:
        intent = command.intent
        if intent is IntentType.COPY_TEXT_TO_CLIPBOARD:
            count = self.clipboard.write(self._required(command, "clipboard_text"))
            return f"Copied {count} characters to the clipboard."
        if intent is IntentType.READ_CLIPBOARD:
            text, truncated = self.clipboard.displayed()
            return f"Clipboard text{' (truncated)' if truncated else ''}:\n{text}"
        if intent is IntentType.CLEAR_CLIPBOARD:
            self.clipboard.clear()
            return "Clipboard text was cleared."
        if intent is IntentType.SEARCH_CLIPBOARD:
            matches = self.clipboard.search(self._required(command, "clipboard_query"))
            return f"Found {len(matches)} clipboard match(es)."
        if intent is IntentType.SAVE_CLIPBOARD_TO_FILE:
            if self.save_text is None:
                raise DesktopUtilityError("Clipboard file saving is unavailable.")
            return self.save_text(
                self._required(command, "clipboard_file"),
                self.clipboard.read(),
                command.command_id,
            )
        if intent is IntentType.CLIPBOARD_TO_NOTE:
            if self.create_note is None:
                raise DesktopUtilityError("Clipboard note creation is unavailable.")
            return self.create_note(
                self._text(command, "note_title") or "Clipboard note",
                self.clipboard.read(),
                command.command_id,
            )
        if intent is IntentType.CAPTURE_SCREENSHOT:
            nums = [
                self._number(command, f"region_{part}")
                for part in ("x", "y", "width", "height")
            ]
            if all(value is not None for value in nums):
                x, y, width, height = nums
                assert x is not None and y is not None
                assert width is not None and height is not None
                request = ScreenshotRequest(
                    ScreenshotTarget.REGION,
                    region=ScreenshotRegion(x, y, width, height),
                )
            elif (display := self._number(command, "display_reference")) is not None:
                request = ScreenshotRequest(
                    ScreenshotTarget.DISPLAY, display_id=str(display)
                )
            elif "virtual desktop" in command.original_text.casefold():
                request = ScreenshotRequest(ScreenshotTarget.VIRTUAL_DESKTOP)
            else:
                request = ScreenshotRequest(ScreenshotTarget.PRIMARY)
            record = self.screenshots.capture(request)
            return f"Screenshot captured as {record.path.name}."
        if intent is IntentType.LIST_SCREENSHOTS:
            items = self.screenshots.recent()
            return (
                "\n".join(f"{i}. {v.path.name}" for i, v in enumerate(items, 1))
                or "No screenshots were captured this session."
            )
        if intent is IntentType.OPEN_SCREENSHOT:
            record = self.screenshots.open_selected(
                self._number(command, "screenshot_reference")
            )
            return f"Opened {record.path.name}."
        if intent is IntentType.DELETE_SCREENSHOT:
            record = self.screenshots.delete_selected()
            return f"Moved {record.path.name} to the recovery location."
        if intent is IntentType.SHOW_DISPLAY_INFORMATION:
            return "\n".join(
                f"{i}. {v.width}x{v.height}{' primary' if v.primary else ''}"
                for i, v in enumerate(self.information.displays(), 1)
            )
        if intent is IntentType.SHOW_ACTIVE_WINDOW:
            return f"Active window: {self.information.active_window().title}"
        if intent in {IntentType.LIST_VISIBLE_WINDOWS, IntentType.FIND_WINDOW}:
            query = (
                self._text(command, "window_query")
                if intent is IntentType.FIND_WINDOW
                else None
            )
            windows = self.information.visible_windows(query)
            return (
                "\n".join(f"{i}. {v.title}" for i, v in enumerate(windows, 1))
                or "No matching visible windows were found."
            )
        item = self.information.select_window(self._number(command, "window_reference"))
        self.information.windows.bring_to_front(item.window_id)
        return f"Brought {item.title} to the front."

    @staticmethod
    def _redacted(command: UserCommand) -> UserCommand:
        text = f"[desktop utility command: {command.intent.value}]"
        return UserCommand(
            text,
            command_id=command.command_id,
            normalized_text=text,
            intent=command.intent,
            confidence=command.confidence,
            received_at=command.received_at,
            source=command.source,
            session_id=command.session_id,
            metadata={"privacy_redacted": True},
        )

    @staticmethod
    def _text(command: UserCommand, name: str) -> str | None:
        return next(
            (
                e.value
                for e in command.entities
                if e.name == name and isinstance(e.value, str)
            ),
            None,
        )

    @classmethod
    def _required(cls, command: UserCommand, name: str) -> str:
        value = cls._text(command, name)
        if value is None:
            raise DesktopUtilityError(f"{name} is required.")
        return value

    @staticmethod
    def _number(command: UserCommand, name: str) -> int | None:
        return next(
            (
                e.value
                for e in command.entities
                if e.name == name
                and isinstance(e.value, int)
                and not isinstance(e.value, bool)
            ),
            None,
        )
