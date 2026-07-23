from __future__ import annotations

import subprocess

import pytest

from omega.system import PowerActionRequest, PowerOperation
from omega.system.controls import (
    SETTINGS_URIS,
    WindowsPowerController,
    WindowsSettingsPageLauncher,
)


def test_settings_launcher_uses_only_allowlisted_uri(monkeypatch) -> None:
    opened: list[str] = []
    launcher = WindowsSettingsPageLauncher(opened.append)
    monkeypatch.setattr("omega.system.controls.sys.platform", "win32")
    launcher.open_page("display")
    assert opened == [SETTINGS_URIS["display"]]

    with pytest.raises(ValueError):
        launcher.open_page("cmd:danger")


def test_power_command_builder_has_fixed_arguments() -> None:
    assert WindowsPowerController.command_for(
        PowerActionRequest(PowerOperation.SHUTDOWN, 10)
    ) == ("shutdown.exe", "/s", "/t", "10")
    assert WindowsPowerController.command_for(
        PowerActionRequest(PowerOperation.RESTART, 5)
    ) == ("shutdown.exe", "/r", "/t", "5")
    assert WindowsPowerController.command_for(
        PowerActionRequest(PowerOperation.CANCEL)
    ) == ("shutdown.exe", "/a")


def test_power_runner_is_shell_false_and_called_once(monkeypatch) -> None:
    calls: list[tuple[tuple[str, ...], dict[str, object]]] = []

    def runner(
        command: tuple[str, ...], **kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        calls.append((command, kwargs))
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr("omega.system.controls.sys.platform", "win32")
    WindowsPowerController(runner).execute(
        PowerActionRequest(PowerOperation.RESTART, 10)
    )
    assert len(calls) == 1
    assert calls[0][1]["shell"] is False
