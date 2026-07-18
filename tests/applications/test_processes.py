from collections.abc import Callable

import psutil

from omega.applications import (
    ApplicationDefinition,
    ApplicationProcess,
    ApplicationProcessService,
)


class FakeProcess:
    def __init__(
        self,
        pid: int,
        name: str,
        *,
        executable: str = "",
        created_at: float = 1.0,
        name_error: Exception | None = None,
        wait_error: Exception | None = None,
    ) -> None:
        self.pid = pid
        self._name = name
        self._executable = executable
        self._created_at = created_at
        self._name_error = name_error
        self._wait_error = wait_error
        self.terminated = False
        self.killed = False

    def name(self) -> str:
        if self._name_error:
            raise self._name_error
        return self._name

    def exe(self) -> str:
        return self._executable

    def create_time(self) -> float:
        return self._created_at

    def terminate(self) -> None:
        self.terminated = True

    def kill(self) -> None:
        self.killed = True

    def wait(self, timeout: float | None = None) -> int | None:
        if self._wait_error:
            raise self._wait_error
        return 0


def _definition(
    process_name: str = "sample.exe", application_id: str = "sample"
) -> ApplicationDefinition:
    return ApplicationDefinition(
        application_id,
        application_id.title(),
        (application_id,),
        executable_names=(process_name,),
        process_names=(process_name,),
        supports_graceful_close=True,
    )


def _factory(processes: list[FakeProcess]) -> Callable[[int], FakeProcess]:
    by_pid = {process.pid: process for process in processes}
    return by_pid.__getitem__


def test_process_matching_is_exact_and_never_uses_substrings() -> None:
    exact = FakeProcess(1, "sample.exe", executable=r"C:\Apps\sample.exe")
    lookalike = FakeProcess(2, "my-sample.exe")
    service = ApplicationProcessService(process_iterator=lambda: [exact, lookalike])

    result = service.inspect(_definition())

    assert [process.pid for process in result.processes] == [1]


def test_trusted_path_rejects_same_named_process_from_another_location() -> None:
    trusted = FakeProcess(1, "sample.exe", executable=r"C:\Apps\sample.exe")
    untrusted = FakeProcess(2, "sample.exe", executable=r"C:\Temp\sample.exe")
    service = ApplicationProcessService(process_iterator=lambda: [trusted, untrusted])

    result = service.inspect(_definition(), r"C:\Apps\sample.exe")

    assert [process.pid for process in result.processes] == [1]


def test_process_inspection_handles_access_denied_and_disappearing_processes() -> None:
    denied = FakeProcess(1, "sample.exe", name_error=psutil.AccessDenied(pid=1))
    gone = FakeProcess(2, "sample.exe", name_error=psutil.NoSuchProcess(pid=2))
    service = ApplicationProcessService(process_iterator=lambda: [denied, gone])

    result = service.inspect(_definition())

    assert result.processes == ()
    assert result.inaccessible_count == 2


def test_graceful_termination_verifies_name_and_creation_time() -> None:
    current = FakeProcess(10, "sample.exe", created_at=5.0)
    stale = FakeProcess(11, "sample.exe", created_at=9.0)
    service = ApplicationProcessService(
        process_iterator=lambda: [], process_factory=_factory([current, stale])
    )
    snapshots = (
        ApplicationProcess(10, "sample.exe", "sample", created_at=5.0),
        ApplicationProcess(11, "sample.exe", "sample", created_at=8.0),
    )

    result = service.terminate(_definition(), snapshots, 1)

    assert result.stopped == 1
    assert result.stale == 1
    assert current.terminated is True
    assert stale.terminated is False


def test_timeout_is_reported_without_automatic_force_close() -> None:
    process = FakeProcess(
        10,
        "sample.exe",
        wait_error=psutil.TimeoutExpired(seconds=1, pid=10),
    )
    service = ApplicationProcessService(
        process_iterator=lambda: [], process_factory=_factory([process])
    )
    snapshot = ApplicationProcess(10, "sample.exe", "sample", created_at=1.0)

    result = service.terminate(_definition(), [snapshot], 1)

    assert result.timed_out == 1
    assert process.terminated is True
    assert process.killed is False


def test_critical_process_is_never_terminated_or_killed() -> None:
    explorer = FakeProcess(20, "explorer.exe", created_at=1.0)
    service = ApplicationProcessService(
        process_iterator=lambda: [], process_factory=_factory([explorer])
    )
    snapshot = ApplicationProcess(20, "explorer.exe", "file_explorer", created_at=1.0)
    definition = _definition("explorer.exe", "file_explorer")

    graceful = service.terminate(definition, [snapshot], 1)
    forced = service.kill(definition, [snapshot], 1)

    assert graceful.protected == 1
    assert forced.protected == 1
    assert explorer.terminated is False
    assert explorer.killed is False
