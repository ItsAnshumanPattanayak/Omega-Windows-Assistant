from pathlib import Path
from tempfile import TemporaryDirectory

from omega.applications import (
    ApplicationDefinition,
    ApplicationLaunchTarget,
    LaunchTargetKind,
    WindowsApplicationLauncher,
)


class FakePopen:
    pid = 321

    def poll(self) -> int | None:
        return None


def _definition() -> ApplicationDefinition:
    return ApplicationDefinition(
        "sample",
        "Sample",
        ("sample",),
        executable_names=("sample.exe",),
        process_names=("sample.exe",),
    )


def test_launcher_uses_argument_sequence_and_shell_false() -> None:
    with TemporaryDirectory(dir=Path.cwd() / "data") as directory:
        executable = Path(directory) / "sample.exe"
        executable.write_bytes(b"test")
        calls: list[tuple[object, object]] = []

        def popen(args: object, *, shell: object) -> FakePopen:
            calls.append((args, shell))
            return FakePopen()

        launcher = WindowsApplicationLauncher(
            platform_name="win32", popen_factory=popen
        )
        result = launcher.launch(
            _definition(),
            ApplicationLaunchTarget(
                "sample", LaunchTargetKind.EXECUTABLE, str(executable)
            ),
        )

        assert result.success is True
        assert result.pid == 321
        assert calls == [([str(executable)], False)]


def test_launcher_handles_permission_failure_and_target_mismatch() -> None:
    with TemporaryDirectory(dir=Path.cwd() / "data") as directory:
        executable = Path(directory) / "sample.exe"
        executable.write_bytes(b"test")

        def denied(*_args: object, **_kwargs: object) -> FakePopen:
            raise PermissionError

        launcher = WindowsApplicationLauncher(
            platform_name="win32", popen_factory=denied
        )
        permission = launcher.launch(
            _definition(),
            ApplicationLaunchTarget(
                "sample", LaunchTargetKind.EXECUTABLE, str(executable)
            ),
        )
        mismatch = launcher.launch(
            _definition(),
            ApplicationLaunchTarget(
                "other", LaunchTargetKind.EXECUTABLE, str(executable)
            ),
        )

        assert permission.permission_denied is True
        assert mismatch.reason == "target_mismatch"


def test_launcher_supports_only_allowlisted_registered_uri() -> None:
    definition = ApplicationDefinition(
        "calculator",
        "Calculator",
        ("calculator",),
        process_names=("CalculatorApp.exe",),
        uri="calculator:",
    )
    calls: list[str] = []
    launcher = WindowsApplicationLauncher(
        platform_name="win32", uri_launcher=calls.append
    )

    result = launcher.launch(
        definition,
        ApplicationLaunchTarget("calculator", LaunchTargetKind.URI, "calculator:"),
    )

    assert result.success is True
    assert result.verified is False
    assert calls == ["calculator:"]


def test_launcher_fails_safely_off_windows() -> None:
    launcher = WindowsApplicationLauncher(platform_name="linux")
    result = launcher.launch(
        _definition(),
        ApplicationLaunchTarget("sample", LaunchTargetKind.EXECUTABLE, "sample.exe"),
    )

    assert result.success is False
    assert result.unsupported_platform is True
