import os
import sys
import time

import pytest

from omega.applications import (
    ApplicationProcessService,
    ApplicationRegistry,
    WindowsApplicationDiscovery,
    WindowsApplicationLauncher,
)

pytestmark = pytest.mark.skipif(
    sys.platform != "win32"
    or os.environ.get("OMEGA_RUN_WINDOWS_INTEGRATION_TESTS") != "1",
    reason="Windows application integration tests are explicit opt-in tests.",
)


def test_calculator_launch_status_and_test_owned_cleanup() -> None:
    """Launch Calculator only when no instance exists; close only new exact PIDs."""
    registry = ApplicationRegistry.from_file()
    definition = registry.get("calculator")
    assert definition is not None
    process_service = ApplicationProcessService()
    before = process_service.inspect(definition)
    if before.processes:
        pytest.skip("Calculator was already running; ownership cannot be guaranteed.")

    discovery = WindowsApplicationDiscovery()
    discovered = discovery.discover(definition)
    if not discovered.found or discovered.target is None:
        pytest.skip("Calculator could not be safely discovered on this Windows host.")
    launcher = WindowsApplicationLauncher()
    launched = launcher.launch(definition, discovered.target)
    if not launched.success:
        pytest.skip("Calculator launch request was not accepted by this Windows host.")

    new_processes = ()
    try:
        time.sleep(2)
        after = process_service.inspect(definition)
        previous_pids = {process.pid for process in before.processes}
        new_processes = tuple(
            process for process in after.processes if process.pid not in previous_pids
        )
        if not new_processes:
            pytest.skip("Calculator PID ownership could not be established reliably.")
        assert all(process.application_id == "calculator" for process in new_processes)
    finally:
        if new_processes:
            closed = process_service.terminate(definition, new_processes, 5)
            assert closed.complete
