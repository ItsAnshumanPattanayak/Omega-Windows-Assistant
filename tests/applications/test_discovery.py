from pathlib import Path
from tempfile import TemporaryDirectory

from omega.applications import (
    ApplicationDefinition,
    LaunchTargetKind,
    WindowsApplicationDiscovery,
)


def _definition(**overrides: object) -> ApplicationDefinition:
    values: dict[str, object] = {
        "application_id": "sample",
        "display_name": "Sample",
        "aliases": ("sample",),
        "executable_names": ("sample.exe",),
        "candidate_paths": (r"%APPROOT%\sample.exe",),
        "process_names": ("sample.exe",),
    }
    values.update(overrides)
    return ApplicationDefinition(**values)  # type: ignore[arg-type]


def test_discovers_environment_candidate_and_caches_it() -> None:
    with TemporaryDirectory(dir=Path.cwd() / "data") as directory:
        root = Path(directory)
        executable = root / "sample.exe"
        executable.write_bytes(b"test")
        discovery = WindowsApplicationDiscovery(
            platform_name="win32",
            environment={"APPROOT": str(root)},
            which=lambda _: None,
        )

        first = discovery.discover(_definition())
        second = discovery.discover(_definition())

        assert first.found is True
        assert first.target.kind is LaunchTargetKind.EXECUTABLE  # type: ignore[union-attr]
        assert second.cached is True
        discovery.invalidate("sample")
        assert discovery.discover(_definition()).cached is False


def test_uses_exact_which_target_and_rejects_wrong_filename() -> None:
    with TemporaryDirectory(dir=Path.cwd() / "data") as directory:
        root = Path(directory)
        executable = root / "sample.exe"
        executable.write_bytes(b"test")
        good = WindowsApplicationDiscovery(
            platform_name="win32", environment={}, which=lambda _: str(executable)
        )
        bad_path = root / "other.exe"
        bad_path.write_bytes(b"test")
        bad = WindowsApplicationDiscovery(
            platform_name="win32", environment={}, which=lambda _: str(bad_path)
        )

        assert good.discover(_definition(candidate_paths=())).found is True
        assert bad.discover(_definition(candidate_paths=())).found is False


def test_uri_allowlist_missing_candidate_and_non_windows_behavior() -> None:
    uri_definition = _definition(
        application_id="calculator",
        aliases=("calculator",),
        executable_names=(),
        candidate_paths=(),
        process_names=("CalculatorApp.exe",),
        uri="calculator:",
    )
    discovery = WindowsApplicationDiscovery(
        platform_name="win32", environment={}, which=lambda _: None
    )
    uri_result = discovery.discover(uri_definition)
    unsupported = WindowsApplicationDiscovery(platform_name="linux").discover(
        uri_definition
    )

    assert uri_result.target.kind is LaunchTargetKind.URI  # type: ignore[union-attr]
    assert unsupported.unsupported_platform is True
    assert unsupported.found is False


def test_discovery_does_not_recursively_scan_drives() -> None:
    calls: list[str] = []
    discovery = WindowsApplicationDiscovery(
        platform_name="win32",
        environment={},
        which=lambda name: calls.append(name) or None,
    )

    result = discovery.discover(_definition(candidate_paths=()))

    assert result.found is False
    assert calls == ["sample.exe"]
