"""Central safety boundary for controlled application operations."""

from __future__ import annotations

import logging
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from time import monotonic, sleep
from typing import Any
from uuid import UUID

from omega.applications.definitions import ApplicationDefinition
from omega.applications.discovery import WindowsApplicationDiscovery
from omega.applications.launcher import WindowsApplicationLauncher
from omega.applications.processes import ApplicationProcessService
from omega.applications.registry import ApplicationRegistry
from omega.applications.results import (
    ApplicationProcess,
    LaunchTargetKind,
    ProcessInspectionResult,
    ProcessOperationResult,
)
from omega.core.exceptions import ApplicationRegistryError
from omega.models import ActionResult, ActionStatus, ErrorCategory, OmegaErrorDetails
from omega.models._serialization import JsonValue, utc_now
from omega.safety.models import ResourceFingerprint


@dataclass(frozen=True)
class ApplicationOperationSettings:
    """Validated timeouts and the global force-close safety switch."""

    launch_verification_timeout_seconds: float = 5.0
    graceful_close_timeout_seconds: float = 5.0
    force_close_timeout_seconds: float = 3.0
    allow_force_close: bool = False

    def __post_init__(self) -> None:
        for name in (
            "launch_verification_timeout_seconds",
            "graceful_close_timeout_seconds",
            "force_close_timeout_seconds",
        ):
            value = getattr(self, name)
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or value <= 0
            ):
                raise ApplicationRegistryError(f"{name} must be positive.")
            object.__setattr__(self, name, float(value))
        if not isinstance(self.allow_force_close, bool):
            raise ApplicationRegistryError("allow_force_close must be a boolean.")

    @classmethod
    def from_mapping(cls, values: Mapping[str, Any]) -> ApplicationOperationSettings:
        return cls(
            launch_verification_timeout_seconds=values.get(
                "launch_verification_timeout_seconds", 5
            ),
            graceful_close_timeout_seconds=values.get(
                "graceful_close_timeout_seconds", 5
            ),
            force_close_timeout_seconds=values.get("force_close_timeout_seconds", 3),
            allow_force_close=values.get("allow_force_close", False),
        )


@dataclass(frozen=True)
class OmegaOwnedProcess:
    application_id: str
    pid: int
    created_at: float
    action_id: UUID


class ApplicationManager:
    """Expose only allowlisted open, status, and guarded close operations."""

    def __init__(
        self,
        registry: ApplicationRegistry,
        discovery: WindowsApplicationDiscovery,
        launcher: WindowsApplicationLauncher,
        process_service: ApplicationProcessService,
        *,
        settings: ApplicationOperationSettings | None = None,
        monotonic_clock: Callable[[], float] = monotonic,
        sleeper: Callable[[float], None] = sleep,
        logger: logging.Logger | None = None,
    ) -> None:
        self.registry = registry
        self.discovery = discovery
        self.launcher = launcher
        self.process_service = process_service
        self.settings = settings or ApplicationOperationSettings()
        self._clock = monotonic_clock
        self._sleep = sleeper
        self._logger = logger or logging.getLogger("omega.applications.manager")
        self._owned: dict[int, OmegaOwnedProcess] = {}

    def clear_pending_confirmations(self) -> None:
        """Compatibility no-op; Phase 7 stores confirmations only centrally."""

    def open_application(
        self, application_id: str, action_id: UUID, command_id: UUID | None = None
    ) -> ActionResult:
        """Launch one enabled registered application without user arguments."""
        definition, failure = self._definition(application_id, action_id, command_id)
        if failure is not None:
            return failure
        assert definition is not None
        inspection = self._inspect(definition)
        if not definition.allow_multiple_instances and inspection.processes:
            return self._success(
                action_id,
                "Application is already running.",
                f"{definition.display_name} is already running.",
                {
                    "application_id": definition.application_id,
                    "outcome": "already_running",
                },
            )
        discovered = self.discovery.discover(definition)
        if not discovered.found or discovered.target is None:
            if discovered.unsupported_platform:
                return self._failure(
                    action_id,
                    command_id,
                    "UNSUPPORTED_PLATFORM",
                    ErrorCategory.UNSUPPORTED,
                    "Application launching is supported only on Windows.",
                    "Application control is available only on Windows.",
                    False,
                )
            return self._failure(
                action_id,
                command_id,
                "APPLICATION_NOT_FOUND",
                ErrorCategory.NOT_FOUND,
                "No safe registered launch target was discovered.",
                f"I could not find {definition.display_name} on this computer.",
                True,
            )
        launched = self.launcher.launch(definition, discovered.target)
        if not launched.success:
            category = (
                ErrorCategory.PERMISSION
                if launched.permission_denied
                else (
                    ErrorCategory.UNSUPPORTED
                    if launched.unsupported_platform
                    else ErrorCategory.EXECUTION
                )
            )
            code = (
                "APPLICATION_PERMISSION_DENIED"
                if launched.permission_denied
                else (
                    "UNSUPPORTED_PLATFORM"
                    if launched.unsupported_platform
                    else "APPLICATION_LAUNCH_FAILED"
                )
            )
            return self._failure(
                action_id,
                command_id,
                code,
                category,
                f"Registered launch request failed: {launched.reason}.",
                f"I could not open {definition.display_name}.",
                True,
            )
        verified = launched.verified or self._wait_for_launch_verification(
            definition, launched.pid
        )
        self._record_owned_process(definition, launched.pid, action_id)
        self._logger.info("Registered application launch succeeded: %s", application_id)
        message = (
            f"Opening {definition.display_name}."
            if verified
            else (
                f"The launch request for {definition.display_name} "
                "was sent successfully."
            )
        )
        return self._success(
            action_id,
            "Registered launch request succeeded.",
            message,
            {
                "application_id": definition.application_id,
                "outcome": "launched",
                "pid": launched.pid,
                "verified": verified,
                "verification_timed_out": not verified,
            },
        )

    def check_application_status(
        self, application_id: str, action_id: UUID, command_id: UUID | None = None
    ) -> ActionResult:
        """Report whether an enabled registered application has exact matches."""
        definition, failure = self._definition(application_id, action_id, command_id)
        if failure is not None:
            return failure
        assert definition is not None
        inspection = self._inspect(definition)
        if inspection.processes:
            return self._success(
                action_id,
                "Registered application is running.",
                f"{definition.display_name} is running.",
                {
                    "application_id": definition.application_id,
                    "running": True,
                    "process_count": len(inspection.processes),
                },
            )
        if inspection.inaccessible_count:
            return self._failure(
                action_id,
                command_id,
                "APPLICATION_STATUS_UNAVAILABLE",
                ErrorCategory.PERMISSION,
                "Process visibility was incomplete during the status check.",
                f"I could not determine the status of {definition.display_name}.",
                True,
            )
        return self._success(
            action_id,
            "Registered application is not running.",
            f"{definition.display_name} is not running.",
            {"application_id": definition.application_id, "running": False},
        )

    def request_close_application(
        self, application_id: str, action_id: UUID, command_id: UUID | None = None
    ) -> ActionResult:
        """Reject legacy direct requests; the central gateway owns confirmation."""
        definition, failure = self._definition(application_id, action_id, command_id)
        if failure is not None:
            return failure
        assert definition is not None
        return self._gateway_required(definition, action_id, command_id)

    def close_application(
        self, application_id: str, action_id: UUID, command_id: UUID | None = None
    ) -> ActionResult:
        """Execute a graceful close only after the central gateway approves it."""
        definition, failure = self._definition(application_id, action_id, command_id)
        if failure is not None:
            return failure
        assert definition is not None
        if not definition.supports_graceful_close:
            return self._blocked_close(definition, action_id, command_id)
        return self._close_now(definition, action_id, command_id)

    def inspect_application_fingerprint(
        self, application_id: str
    ) -> ResourceFingerprint:
        """Capture process identity for central confirmation revalidation."""
        definition = self.registry.get(application_id)
        if definition is None:
            return ResourceFingerprint("application", application_id, False)
        inspection = self._inspect(definition)
        identities = tuple(
            sorted(
                (process.pid, process.created_at or 0.0)
                for process in inspection.processes
            )
        )
        identity = f"{application_id}:{identities!r}"
        return ResourceFingerprint(
            "application",
            identity,
            bool(inspection.processes),
            item_count=len(inspection.processes),
        )

    def confirm_close_application(
        self, application_id: str, action_id: UUID, command_id: UUID | None = None
    ) -> ActionResult:
        """Reject legacy confirmation; only ConfirmationManager can approve."""
        definition, failure = self._definition(application_id, action_id, command_id)
        if failure is not None:
            return failure
        assert definition is not None
        return self._gateway_required(definition, action_id, command_id)

    def cancel_close_application(
        self, application_id: str, action_id: UUID, command_id: UUID | None = None
    ) -> ActionResult:
        definition, failure = self._definition(application_id, action_id, command_id)
        if failure is not None:
            return failure
        assert definition is not None
        return self._gateway_required(definition, action_id, command_id)

    def request_force_close_application(
        self, application_id: str, action_id: UUID, command_id: UUID | None = None
    ) -> ActionResult:
        """Deny force close at the domain boundary in Phase 7."""
        definition, failure = self._definition(application_id, action_id, command_id)
        if failure is not None:
            return failure
        assert definition is not None
        return self._failure(
            action_id,
            command_id,
            "FORCE_CLOSE_DISABLED",
            ErrorCategory.SAFETY,
            "Force close is disabled by central Phase 7 policy.",
            f"Omega does not force close {definition.display_name}.",
            False,
        )

    def confirm_force_close_application(
        self, application_id: str, action_id: UUID, command_id: UUID | None = None
    ) -> ActionResult:
        """Deny force close even if a legacy caller tries to confirm it."""
        definition, failure = self._definition(application_id, action_id, command_id)
        if failure is not None:
            return failure
        assert definition is not None
        return self._failure(
            action_id,
            command_id,
            "FORCE_CLOSE_DISABLED",
            ErrorCategory.SAFETY,
            "Force close is disabled by central Phase 7 policy.",
            f"Omega does not force close {definition.display_name}.",
            False,
        )

    def cancel_force_close_application(
        self, application_id: str, action_id: UUID, command_id: UUID | None = None
    ) -> ActionResult:
        return self.request_force_close_application(
            application_id, action_id, command_id
        )

    def _close_now(
        self,
        definition: ApplicationDefinition,
        action_id: UUID,
        command_id: UUID | None,
    ) -> ActionResult:
        inspection = self._inspect(definition)
        if not inspection.processes:
            if inspection.inaccessible_count:
                return self._close_visibility_failure(definition, action_id, command_id)
            return self._success(
                action_id,
                "Application was not running.",
                f"{definition.display_name} is not currently running.",
                {"application_id": definition.application_id, "outcome": "not_running"},
            )
        targets = self._preferred_targets(definition, inspection.processes)
        result = self.process_service.terminate(
            definition, targets, self.settings.graceful_close_timeout_seconds
        )
        if result.complete:
            self._remove_owned(targets)
            self._logger.info("Application closed: %s", definition.application_id)
            return self._success(
                action_id,
                "Application closed gracefully.",
                f"{definition.display_name} has been closed.",
                self._operation_data(definition, result, "closed"),
            )
        return self._operation_failure(
            definition, result, action_id, command_id, force=False
        )

    def _inspect(self, definition: ApplicationDefinition) -> ProcessInspectionResult:
        discovered = self.discovery.discover(definition)
        trusted_path = (
            discovered.target.value
            if definition.validate_process_path
            and discovered.target is not None
            and discovered.target.kind is LaunchTargetKind.EXECUTABLE
            else None
        )
        return self.process_service.inspect(definition, trusted_path)

    def _wait_for_launch_verification(
        self, definition: ApplicationDefinition, launched_pid: int | None
    ) -> bool:
        deadline = self._clock() + self.settings.launch_verification_timeout_seconds
        while self._clock() < deadline:
            inspection = self._inspect(definition)
            if launched_pid is None and inspection.processes:
                return True
            if launched_pid is not None and any(
                process.pid == launched_pid for process in inspection.processes
            ):
                return True
            remaining = deadline - self._clock()
            if remaining <= 0:
                break
            self._sleep(min(0.1, remaining))
        self._logger.warning(
            "Application launch could not be verified: %s",
            definition.application_id,
        )
        return False

    def _preferred_targets(
        self,
        definition: ApplicationDefinition,
        snapshots: tuple[ApplicationProcess, ...],
    ) -> tuple[ApplicationProcess, ...]:
        owned: list[ApplicationProcess] = []
        for snapshot in snapshots:
            record = self._owned.get(snapshot.pid)
            if (
                record is not None
                and record.application_id == definition.application_id
                and snapshot.created_at is not None
                and abs(snapshot.created_at - record.created_at) <= 0.001
            ):
                owned.append(snapshot)
            elif record is not None:
                self._owned.pop(snapshot.pid, None)
        return tuple(owned) or snapshots

    def _record_owned_process(
        self, definition: ApplicationDefinition, pid: int | None, action_id: UUID
    ) -> None:
        if pid is None:
            return
        inspection = self._inspect(definition)
        snapshot = next(
            (
                process
                for process in inspection.processes
                if process.pid == pid and process.created_at is not None
            ),
            None,
        )
        if snapshot is not None and snapshot.created_at is not None:
            self._owned[pid] = OmegaOwnedProcess(
                definition.application_id, pid, snapshot.created_at, action_id
            )

    def _remove_owned(self, processes: tuple[ApplicationProcess, ...]) -> None:
        for process in processes:
            self._owned.pop(process.pid, None)

    def _definition(
        self, application_id: str, action_id: UUID, command_id: UUID | None
    ) -> tuple[ApplicationDefinition | None, ActionResult | None]:
        definition = self.registry.get(application_id)
        if definition is not None:
            return definition, None
        configured = self.registry.get(application_id, include_disabled=True)
        if configured is not None:
            return None, self._failure(
                action_id,
                command_id,
                "APPLICATION_DISABLED",
                ErrorCategory.PERMISSION,
                "The registered application is disabled.",
                f"{configured.display_name} is disabled in Omega's registry.",
                False,
            )
        return None, self._failure(
            action_id,
            command_id,
            "APPLICATION_NOT_REGISTERED",
            ErrorCategory.UNSUPPORTED,
            "The application ID is not registered.",
            "That application is not registered for Omega to control.",
            False,
        )

    def _gateway_required(
        self,
        definition: ApplicationDefinition,
        action_id: UUID,
        command_id: UUID | None,
    ) -> ActionResult:
        return self._failure(
            action_id,
            command_id,
            "CENTRAL_GATEWAY_REQUIRED",
            ErrorCategory.SAFETY,
            "Direct application confirmation is disabled in Phase 7.",
            f"A central safety confirmation is required for {definition.display_name}.",
            True,
        )

    def _blocked_close(
        self,
        definition: ApplicationDefinition,
        action_id: UUID,
        command_id: UUID | None,
    ) -> ActionResult:
        user_message = (
            "Omega does not close Windows File Explorer because it may affect the "
            "Windows desktop."
            if definition.application_id == "file_explorer"
            else f"Omega does not close {definition.display_name} in this phase."
        )
        return self._failure(
            action_id,
            command_id,
            "APPLICATION_CLOSE_BLOCKED",
            ErrorCategory.SAFETY,
            "The registered application is protected from closing.",
            user_message,
            False,
        )

    def _operation_failure(
        self,
        definition: ApplicationDefinition,
        result: ProcessOperationResult,
        action_id: UUID,
        command_id: UUID | None,
        *,
        force: bool,
    ) -> ActionResult:
        if result.access_denied:
            user_message = (
                f"I could not close {definition.display_name} "
                "because access was denied."
            )
            code = "APPLICATION_CLOSE_ACCESS_DENIED"
            category = ErrorCategory.PERMISSION
        elif result.timed_out:
            user_message = (
                f"Some {definition.display_name} processes could not be closed."
            )
            code = "APPLICATION_CLOSE_TIMEOUT"
            category = ErrorCategory.TIMEOUT
        else:
            user_message = (
                f"Some {definition.display_name} processes could not be closed."
            )
            code = "APPLICATION_CLOSE_PARTIAL"
            category = ErrorCategory.EXECUTION
        return self._failure(
            action_id,
            command_id,
            code,
            category,
            "Controlled process close was incomplete.",
            user_message,
            True,
            self._operation_data(
                definition, result, "force_close_failed" if force else "close_failed"
            ),
        )

    def _close_visibility_failure(
        self,
        definition: ApplicationDefinition,
        action_id: UUID,
        command_id: UUID | None,
    ) -> ActionResult:
        return self._failure(
            action_id,
            command_id,
            "APPLICATION_CLOSE_STATUS_UNAVAILABLE",
            ErrorCategory.PERMISSION,
            "Process visibility was incomplete before the close request.",
            f"I could not safely determine which {definition.display_name} "
            "processes could be closed.",
            True,
        )

    @staticmethod
    def _operation_data(
        definition: ApplicationDefinition,
        result: ProcessOperationResult,
        outcome: str,
    ) -> dict[str, JsonValue]:
        return {
            "application_id": definition.application_id,
            "outcome": outcome,
            "attempted": result.attempted,
            "stopped": result.stopped,
            "access_denied": result.access_denied,
            "timed_out": result.timed_out,
            "stale": result.stale,
            "protected": result.protected,
        }

    @staticmethod
    def _success(
        action_id: UUID,
        message: str,
        user_message: str,
        data: JsonValue,
    ) -> ActionResult:
        return ActionResult.success_result(action_id, message, user_message, data=data)

    @staticmethod
    def _failure(
        action_id: UUID,
        command_id: UUID | None,
        code: str,
        category: ErrorCategory,
        message: str,
        user_message: str,
        recoverable: bool,
        data: JsonValue = None,
    ) -> ActionResult:
        timestamp = utc_now()
        error = OmegaErrorDetails(
            code=code,
            category=category,
            message=message,
            user_message=user_message,
            recoverable=recoverable,
            action_id=action_id,
            command_id=command_id,
        )
        return ActionResult(
            action_id=action_id,
            success=False,
            status=ActionStatus.FAILED,
            message=message,
            user_message=user_message,
            data=data,
            error=error,
            started_at=timestamp,
            completed_at=timestamp,
            duration_ms=0,
        )
