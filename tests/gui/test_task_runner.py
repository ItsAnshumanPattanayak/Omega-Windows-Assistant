from threading import Event, get_ident

import pytest

from omega.core.exceptions import GuiTaskError
from omega.gui import GuiTaskRunner


def test_result_and_error_are_marshalled_once():
    succeeded = []
    failed = []
    runner = GuiTaskRunner(maximum_workers=1)

    success = runner.submit(lambda: 7, succeeded.append, failed.append)
    assert success.result(timeout=2) == 7
    assert runner.drain_callbacks() == 1
    assert succeeded == [7] and failed == []

    def fail():
        raise RuntimeError("failed")

    failure = runner.submit(fail, succeeded.append, failed.append)
    with pytest.raises(RuntimeError):
        failure.result(timeout=2)
    assert runner.drain_callbacks() == 1
    assert len(failed) == 1
    runner.shutdown(wait=True)


def test_callback_executes_only_on_draining_thread():
    callback_threads = []
    runner = GuiTaskRunner(maximum_workers=1)
    future = runner.submit(
        lambda: get_ident(),
        lambda _worker_thread: callback_threads.append(get_ident()),
        lambda _error: None,
    )
    worker_thread = future.result(timeout=2)
    draining_thread = get_ident()

    assert callback_threads == []
    runner.drain_callbacks()
    assert callback_threads == [draining_thread]
    assert worker_thread != draining_thread
    runner.shutdown(wait=True)


def test_bounded_workers_and_shutdown():
    with pytest.raises(GuiTaskError):
        GuiTaskRunner(maximum_workers=5)

    gate = Event()
    runner = GuiTaskRunner(maximum_workers=1)
    runner.submit(lambda: gate.wait(1), lambda _value: None, lambda _error: None)
    runner.shutdown(wait=False)
    gate.set()
    with pytest.raises(GuiTaskError):
        runner.submit(lambda: None, lambda _value: None, lambda _error: None)
