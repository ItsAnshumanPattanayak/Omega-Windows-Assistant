"""Module and console-script entry point for Omega."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Callable, Sequence
from typing import Protocol

from omega.core.exceptions import OmegaError


class _AudioDevice(Protocol):
    @property
    def identifier(self) -> int: ...

    @property
    def name(self) -> str: ...

    @property
    def input_channels(self) -> int: ...

    @property
    def default_sample_rate_hz(self) -> int: ...


class _Application(Protocol):
    def run(self) -> int: ...
    def run_gui(self) -> int: ...
    def run_voice(self) -> int: ...
    def list_audio_devices(self) -> Sequence[_AudioDevice]: ...


# Injectable seam for entry-point tests; production resolves the class lazily.
OmegaApplication: Callable[[], _Application] | None = None


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="omega",
        description="Omega safety-first Windows assistant",
        add_help=False,
    )
    parser.add_argument("-h", "--help", action="store_true")
    parser.add_argument(
        "--gui",
        action="store_true",
        help="start the optional tkinter desktop interface",
    )
    parser.add_argument(
        "--voice",
        action="store_true",
        help="start explicit offline voice mode",
    )
    parser.add_argument(
        "--list-audio-devices",
        action="store_true",
        help="list bounded microphone metadata and exit",
    )
    parser.add_argument(
        "--gui-check",
        action="store_true",
        help="check tkinter availability without starting Omega",
    )
    parser.add_argument(
        "--security-check",
        action="store_true",
        help="run bounded, read-only local security diagnostics and exit",
    )
    parser.add_argument(
        "--performance-check",
        action="store_true",
        help="run bounded, read-only local performance diagnostics and exit",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Initialize terminal or explicitly requested GUI mode."""

    arguments = list(sys.argv[1:] if argv is None else argv)
    parser = _parser()
    options, unknown = parser.parse_known_args(arguments)
    if options.help:
        parser.print_help()
        return 0
    selected_modes = sum(
        bool(value)
        for value in (
            options.gui,
            options.gui_check,
            options.security_check,
            options.performance_check,
            options.voice,
            options.list_audio_devices,
        )
    )
    if unknown or selected_modes > 1:
        detail = " ".join(unknown) if unknown else "choose one startup mode"
        print(f"Omega argument error: {detail}", file=sys.stderr)
        parser.print_usage(sys.stderr)
        return 2
    try:
        if options.performance_check:
            from omega.config import load_settings
            from omega.performance.diagnostics import (
                PerformanceDiagnostics,
                format_performance_report,
            )
            from omega.utils.paths import project_root

            settings = load_settings()
            performance_report = PerformanceDiagnostics(
                settings.performance_configuration,
                repository_root=project_root(),
            ).run(settings)
            print(format_performance_report(performance_report))
            return 0 if performance_report.available else 1
        if options.security_check:
            from omega.config import load_settings
            from omega.security.diagnostics import (
                SecurityDiagnostics,
                format_security_report,
            )
            from omega.utils.paths import project_root

            settings = load_settings()
            security_report = SecurityDiagnostics(
                settings.security_configuration,
                repository_root=project_root(),
            ).run(settings)
            print(format_security_report(security_report))
            return 0 if security_report.passed else 1
        if options.gui_check:
            from omega.gui.application import OmegaGuiApplication

            OmegaGuiApplication.check_available()
            print("Omega GUI support is available.")
            return 0
        if OmegaApplication is None:
            from omega.app import OmegaApplication as ConcreteApplication

            application: _Application = ConcreteApplication()
        else:
            application = OmegaApplication()
        if options.list_audio_devices:
            devices = application.list_audio_devices()
            if not devices:
                print("No microphone input devices were found.")
            for device in devices:
                print(
                    f"{device.identifier}: {device.name} "
                    f"({device.input_channels} input channel(s), "
                    f"{device.default_sample_rate_hz} Hz)"
                )
            return 0
        if options.voice:
            return application.run_voice()
        return application.run_gui() if options.gui else application.run()
    except OmegaError as error:
        print(f"Omega initialization failed: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
