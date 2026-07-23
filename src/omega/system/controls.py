"""Lazy, tightly bounded Windows control adapters."""

from __future__ import annotations

import ctypes
import os
import subprocess
import sys
from collections.abc import Callable

from omega.core.exceptions import OmegaError
from omega.system.models import (
    AudioState,
    BrightnessState,
    PowerActionRequest,
    PowerOperation,
)


class UnsupportedDeviceError(OmegaError):
    """Raised when a safe local adapter is unavailable."""


class UnavailableAudioController:
    """Fail safely when no compatible local audio adapter is installed."""

    def get_state(self) -> AudioState:
        raise UnsupportedDeviceError("Windows audio control is unavailable.")

    def set_volume(self, percent: int) -> AudioState:
        del percent
        raise UnsupportedDeviceError("Windows audio control is unavailable.")

    def set_muted(self, muted: bool) -> AudioState:
        del muted
        raise UnsupportedDeviceError("Windows audio control is unavailable.")


class UnavailableBrightnessController:
    """Fail safely when no compatible local brightness adapter is installed."""

    def get_state(self) -> BrightnessState:
        raise UnsupportedDeviceError("Windows brightness control is unavailable.")

    def set_brightness(self, percent: int) -> BrightnessState:
        del percent
        raise UnsupportedDeviceError("Windows brightness control is unavailable.")


SETTINGS_URIS = {
    "system": "ms-settings:system",
    "display": "ms-settings:display",
    "sound": "ms-settings:sound",
    "notifications": "ms-settings:notifications",
    "power": "ms-settings:powersleep",
    "storage": "ms-settings:storagesense",
    "bluetooth": "ms-settings:bluetooth",
    "network": "ms-settings:network",
    "windows_update": "ms-settings:windowsupdate",
    "apps": "ms-settings:appsfeatures",
    "privacy": "ms-settings:privacy",
}


class WindowsSettingsPageLauncher:
    """Open only constant, allowlisted Windows Settings URIs."""

    def __init__(self, starter: Callable[[str], object] | None = None) -> None:
        self._starter = starter

    def open_page(self, page: str) -> None:
        uri = SETTINGS_URIS.get(page)
        if uri is None:
            raise ValueError("Unknown Windows Settings page.")
        if sys.platform != "win32":
            raise UnsupportedDeviceError("Windows Settings is unavailable.")
        starter = self._starter or os.startfile
        starter(uri)


class WindowsPowerController:
    """Execute only fixed Windows power operations; never accepts command text."""

    def __init__(
        self,
        runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
    ) -> None:
        self._runner = runner

    @staticmethod
    def command_for(request: PowerActionRequest) -> tuple[str, ...] | None:
        if request.operation is PowerOperation.SHUTDOWN:
            return ("shutdown.exe", "/s", "/t", str(request.countdown_seconds))
        if request.operation is PowerOperation.RESTART:
            return ("shutdown.exe", "/r", "/t", str(request.countdown_seconds))
        if request.operation is PowerOperation.SIGN_OUT:
            return ("shutdown.exe", "/l")
        if request.operation is PowerOperation.CANCEL:
            return ("shutdown.exe", "/a")
        return None

    def execute(self, request: PowerActionRequest) -> None:
        if sys.platform != "win32":
            raise UnsupportedDeviceError("Windows power controls are unavailable.")
        command = self.command_for(request)
        if command is not None:
            self._runner(
                command,
                shell=False,
                check=True,
                capture_output=True,
                text=True,
                timeout=10,
            )
            return
        if request.operation is PowerOperation.LOCK:
            if ctypes.windll.user32.LockWorkStation() == 0:
                raise OSError("Windows did not accept the lock request.")
            return
        if request.operation in {PowerOperation.SLEEP, PowerOperation.HIBERNATE}:
            hibernate = request.operation is PowerOperation.HIBERNATE
            if ctypes.windll.powrprof.SetSuspendState(hibernate, False, False) == 0:
                raise OSError("Windows did not accept the suspend request.")
            return
        raise ValueError("Unsupported power operation.")
