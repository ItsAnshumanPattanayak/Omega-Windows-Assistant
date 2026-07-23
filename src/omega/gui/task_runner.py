"""Bounded worker execution with callbacks queued for the UI thread."""

from __future__ import annotations

from collections.abc import Callable
from concurrent.futures import Future, ThreadPoolExecutor
from functools import partial
from queue import Empty, Queue
from threading import Lock
from typing import TypeVar

from omega.core.exceptions import GuiTaskError

T = TypeVar("T")


class GuiTaskRunner:
    """Run blocking work off the UI thread and deliver one callback."""

    def __init__(
        self,
        *,
        maximum_workers: int = 2,
    ) -> None:
        if isinstance(maximum_workers, bool) or not 1 <= maximum_workers <= 4:
            raise GuiTaskError("GUI worker count must be between 1 and 4.")
        self._executor = ThreadPoolExecutor(
            max_workers=maximum_workers,
            thread_name_prefix="omega-gui",
        )
        self._lock = Lock()
        self._callbacks: Queue[Callable[[], None]] = Queue()
        self._closed = False

    def submit(
        self,
        operation: Callable[[], T],
        on_success: Callable[[T], None],
        on_error: Callable[[BaseException], None],
    ) -> Future[T]:
        """Schedule one operation and marshal exactly one terminal callback."""

        with self._lock:
            if self._closed:
                raise GuiTaskError("The GUI task runner is closed.")
            future = self._executor.submit(operation)

        def done(completed: Future[T]) -> None:
            with self._lock:
                if self._closed:
                    return
            try:
                value = completed.result()
            except BaseException as error:
                self._callbacks.put(partial(on_error, error))
            else:
                self._callbacks.put(partial(on_success, value))

        future.add_done_callback(done)
        return future

    def drain_callbacks(self, *, maximum: int = 100) -> int:
        """Run queued terminal callbacks on the caller's UI thread."""

        if isinstance(maximum, bool) or not 1 <= maximum <= 1000:
            raise GuiTaskError("GUI callback batch must be between 1 and 1000.")
        completed = 0
        while completed < maximum:
            try:
                callback = self._callbacks.get_nowait()
            except Empty:
                break
            callback()
            completed += 1
        return completed

    def shutdown(self, *, wait: bool = False) -> None:
        """Prevent new work and release executor resources without retry."""

        with self._lock:
            if self._closed:
                return
            self._closed = True
        self._executor.shutdown(wait=wait, cancel_futures=True)
