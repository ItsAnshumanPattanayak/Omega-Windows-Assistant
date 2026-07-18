from uuid import uuid4

import pytest

from omega.applications import (
    ApplicationDefinition,
    ApplicationDiscoveryResult,
    ApplicationLaunchResult,
    ApplicationLaunchTarget,
    ApplicationManager,
    ApplicationOperationSettings,
    ApplicationProcess,
    ApplicationRegistry,
    LaunchTargetKind,
    ProcessInspectionResult,
    ProcessOperationResult,
)
from omega.core.exceptions import ApplicationRegistryError


def _definition(
    application_id: str = "sample",
    *,
    confirmation: bool = False,
    close: bool = True,
    force: bool = False,
    enabled: bool = True,
    process_name: str | None = None,
) -> ApplicationDefinition:
    executable = process_name or f"{application_id}.exe"
    return ApplicationDefinition(
        application_id,
        application_id.replace("_", " ").title(),
        (application_id.replace("_", " "),),
        executable_names=(executable,),
        process_names=(executable,),
        supports_graceful_close=close,
        requires_close_confirmation=confirmation,
        allow_force_close=force,
        enabled=enabled,
    )


class FakeDiscovery:
    def __init__(self, found: bool = True) -> None:
        self.found = found

    def discover(self, definition: ApplicationDefinition) -> ApplicationDiscoveryResult:
        target = (
            ApplicationLaunchTarget(
                definition.application_id,
                LaunchTargetKind.EXECUTABLE,
                rf"C:\Apps\{definition.executable_names[0]}",
            )
            if self.found
            else None
        )
        return ApplicationDiscoveryResult(
            self.found,
            definition.application_id,
            target,
            None if self.found else "not_found",
        )


class FakeLauncher:
    def __init__(self, result: ApplicationLaunchResult | None = None) -> None:
        self.result = result
        self.calls: list[str] = []

    def launch(
        self, definition: ApplicationDefinition, _target: ApplicationLaunchTarget
    ) -> ApplicationLaunchResult:
        self.calls.append(definition.application_id)
        return self.result or ApplicationLaunchResult(
            True, definition.application_id, pid=42, verified=True
        )


class FakeProcessService:
    def __init__(
        self,
        inspection: ProcessInspectionResult | None = None,
        terminate_result: ProcessOperationResult | None = None,
        kill_result: ProcessOperationResult | None = None,
    ) -> None:
        self.inspection = inspection or ProcessInspectionResult()
        self.terminate_result = terminate_result or ProcessOperationResult(
            attempted=1, stopped=1
        )
        self.kill_result = kill_result or ProcessOperationResult(attempted=1, stopped=1)
        self.terminated: tuple[ApplicationProcess, ...] = ()
        self.killed: tuple[ApplicationProcess, ...] = ()

    def inspect(
        self,
        _definition: ApplicationDefinition,
        _trusted_path: str | None = None,
    ) -> ProcessInspectionResult:
        return self.inspection

    def terminate(
        self,
        _definition: ApplicationDefinition,
        processes: tuple[ApplicationProcess, ...],
        _timeout: float,
    ) -> ProcessOperationResult:
        self.terminated = tuple(processes)
        return self.terminate_result

    def kill(
        self,
        _definition: ApplicationDefinition,
        processes: tuple[ApplicationProcess, ...],
        _timeout: float,
    ) -> ProcessOperationResult:
        self.killed = tuple(processes)
        return self.kill_result


def _manager(
    definition: ApplicationDefinition,
    *,
    discovery: FakeDiscovery | None = None,
    launcher: FakeLauncher | None = None,
    processes: FakeProcessService | None = None,
    settings: ApplicationOperationSettings | None = None,
    clock=lambda: 0.0,
    sleeper=lambda _seconds: None,
) -> tuple[ApplicationManager, FakeLauncher, FakeProcessService]:
    fake_launcher = launcher or FakeLauncher()
    fake_processes = processes or FakeProcessService()
    manager = ApplicationManager(
        ApplicationRegistry([definition]),
        discovery or FakeDiscovery(),  # type: ignore[arg-type]
        fake_launcher,  # type: ignore[arg-type]
        fake_processes,  # type: ignore[arg-type]
        settings=settings,
        monotonic_clock=clock,
        sleeper=sleeper,
    )
    return manager, fake_launcher, fake_processes


def test_open_launches_registered_target_and_handles_duplicate() -> None:
    definition = _definition()
    manager, launcher, _ = _manager(definition)

    opened = manager.open_application("sample", uuid4(), uuid4())

    assert opened.success is True
    assert opened.data["application_id"] == "sample"  # type: ignore[index]
    assert launcher.calls == ["sample"]

    running = ApplicationProcess(5, "sample.exe", "sample", created_at=1.0)
    duplicate_manager, duplicate_launcher, _ = _manager(
        definition,
        processes=FakeProcessService(ProcessInspectionResult((running,))),
    )
    duplicate = duplicate_manager.open_application("sample", uuid4())
    assert "already running" in duplicate.user_message
    assert duplicate_launcher.calls == []


def test_open_reports_unknown_missing_and_disabled_applications() -> None:
    definition = _definition()
    manager, _, _ = _manager(definition, discovery=FakeDiscovery(False))

    assert manager.open_application("unknown", uuid4()).success is False
    assert "could not find" in manager.open_application("sample", uuid4()).user_message

    disabled_manager, _, _ = _manager(_definition(enabled=False))
    disabled = disabled_manager.open_application("sample", uuid4())
    assert disabled.error.code == "APPLICATION_DISABLED"  # type: ignore[union-attr]


def test_unverified_launch_uses_timeout_without_claiming_process_success() -> None:
    clock = [0.0]
    launcher = FakeLauncher(ApplicationLaunchResult(True, "sample", verified=False))
    manager, _, _ = _manager(
        _definition(),
        launcher=launcher,
        settings=ApplicationOperationSettings(launch_verification_timeout_seconds=0.2),
        clock=lambda: clock[0],
        sleeper=lambda seconds: clock.__setitem__(0, clock[0] + seconds),
    )

    result = manager.open_application("sample", uuid4())

    assert result.success is True
    assert "request" in result.user_message
    assert result.data["verified"] is False  # type: ignore[index]
    assert result.data["verification_timed_out"] is True  # type: ignore[index]


def test_status_reports_running_not_running_and_incomplete_visibility() -> None:
    definition = _definition()
    running = ApplicationProcess(5, "sample.exe", "sample", created_at=1.0)
    running_manager, _, _ = _manager(
        definition,
        processes=FakeProcessService(ProcessInspectionResult((running,))),
    )
    stopped_manager, _, _ = _manager(definition)
    hidden_manager, _, _ = _manager(
        definition,
        processes=FakeProcessService(ProcessInspectionResult((), 1)),
    )

    assert (
        "is running"
        in running_manager.check_application_status("sample", uuid4()).user_message
    )
    assert (
        "not running"
        in stopped_manager.check_application_status("sample", uuid4()).user_message
    )
    assert (
        "could not determine"
        in hidden_manager.check_application_status("sample", uuid4()).user_message
    )


def test_legacy_close_confirmation_methods_fail_closed() -> None:
    definition = _definition(confirmation=True)
    process = ApplicationProcess(5, "sample.exe", "sample", created_at=1.0)
    manager, _, service = _manager(
        definition,
        processes=FakeProcessService(ProcessInspectionResult((process,))),
    )

    requested = manager.request_close_application("sample", uuid4())
    assert "central safety confirmation" in requested.user_message
    assert service.terminated == ()
    confirmed = manager.confirm_close_application("sample", uuid4())
    assert confirmed.success is False
    assert service.terminated == ()

    manager.request_close_application("sample", uuid4())
    cancelled = manager.cancel_close_application("sample", uuid4())
    assert "central safety confirmation" in cancelled.user_message
    assert manager.confirm_close_application("sample", uuid4()).success is False


def test_legacy_confirmation_never_creates_expiring_state() -> None:
    clock = [0.0]
    definition = _definition(confirmation=True)
    process = ApplicationProcess(5, "sample.exe", "sample", created_at=1.0)
    manager, _, service = _manager(
        definition,
        processes=FakeProcessService(ProcessInspectionResult((process,))),
        settings=ApplicationOperationSettings(),
        clock=lambda: clock[0],
    )
    manager.request_close_application("sample", uuid4())
    clock[0] = 2.1

    result = manager.confirm_close_application("sample", uuid4())

    assert "central safety confirmation" in result.user_message
    assert service.terminated == ()


def test_confirmation_for_one_application_cannot_close_another() -> None:
    sample = _definition(confirmation=True)
    other = _definition("other", confirmation=True)
    process = ApplicationProcess(5, "sample.exe", "sample", created_at=1.0)
    service = FakeProcessService(ProcessInspectionResult((process,)))
    registry = ApplicationRegistry([sample, other])
    manager = ApplicationManager(
        registry,
        FakeDiscovery(),  # type: ignore[arg-type]
        FakeLauncher(),  # type: ignore[arg-type]
        service,  # type: ignore[arg-type]
    )
    manager.request_close_application("sample", uuid4())

    wrong = manager.confirm_close_application("other", uuid4())

    assert wrong.success is False
    assert service.terminated == ()
    assert manager.confirm_close_application("sample", uuid4()).success is False


def test_direct_close_request_never_executes_or_forces() -> None:
    process = ApplicationProcess(5, "sample.exe", "sample", created_at=1.0)
    service = FakeProcessService(
        ProcessInspectionResult((process,)),
        terminate_result=ProcessOperationResult(attempted=1, timed_out=1),
    )
    manager, _, service = _manager(_definition(), processes=service)

    result = manager.request_close_application("sample", uuid4())

    assert result.success is False
    assert "central safety confirmation" in result.user_message
    assert service.terminated == ()
    assert service.killed == ()


def test_direct_close_does_not_inspect_incomplete_process_visibility() -> None:
    service = FakeProcessService(ProcessInspectionResult((), 1))
    manager, _, service = _manager(_definition(), processes=service)

    result = manager.request_close_application("sample", uuid4())

    assert result.success is False
    assert "central safety confirmation" in result.user_message
    assert service.terminated == ()


def test_force_close_remains_impossible_even_if_legacy_settings_enable_it() -> None:
    process = ApplicationProcess(5, "sample.exe", "sample", created_at=1.0)
    service = FakeProcessService(
        ProcessInspectionResult((process,)),
        terminate_result=ProcessOperationResult(attempted=1, timed_out=1),
    )
    enabled_settings = ApplicationOperationSettings(allow_force_close=True)
    manager, _, service = _manager(
        _definition(force=True), processes=service, settings=enabled_settings
    )

    assert manager.request_force_close_application("sample", uuid4()).success is False
    manager.request_close_application("sample", uuid4())
    requested = manager.request_force_close_application("sample", uuid4())
    assert "does not force close" in requested.user_message
    confirmed = manager.confirm_force_close_application("sample", uuid4())
    assert confirmed.success is False
    assert service.killed == ()

    disabled, _, _ = _manager(
        _definition(force=True),
        processes=service,
        settings=ApplicationOperationSettings(allow_force_close=False),
    )
    assert disabled.request_force_close_application("sample", uuid4()).success is False


def test_file_explorer_direct_close_is_blocked_before_process_mutation() -> None:
    explorer = _definition("file_explorer", close=False, process_name="explorer.exe")
    process = ApplicationProcess(5, "explorer.exe", "file_explorer", created_at=1.0)
    manager, _, service = _manager(
        explorer,
        processes=FakeProcessService(ProcessInspectionResult((process,))),
    )

    result = manager.request_close_application("file_explorer", uuid4())

    assert "central safety confirmation" in result.user_message
    assert service.terminated == ()
    assert service.killed == ()


@pytest.mark.parametrize(
    "values",
    [
        {"launch_verification_timeout_seconds": 0},
        {"graceful_close_timeout_seconds": -1},
        {"allow_force_close": "yes"},
    ],
)
def test_application_operation_settings_reject_unsafe_values(
    values: dict[str, object],
) -> None:
    with pytest.raises(ApplicationRegistryError):
        ApplicationOperationSettings.from_mapping(values)
