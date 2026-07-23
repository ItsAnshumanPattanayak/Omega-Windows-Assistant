"""Module and console-script entry point for Omega."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence

from omega.app import OmegaApplication
from omega.core.exceptions import OmegaError


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
        "--gui-check",
        action="store_true",
        help="check tkinter availability without starting Omega",
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
    if unknown or (options.gui and options.gui_check):
        detail = " ".join(unknown) if unknown else "choose one GUI option"
        print(f"Omega argument error: {detail}", file=sys.stderr)
        parser.print_usage(sys.stderr)
        return 2
    try:
        if options.gui_check:
            from omega.gui.application import OmegaGuiApplication

            OmegaGuiApplication.check_available()
            print("Omega GUI support is available.")
            return 0
        application = OmegaApplication()
        return application.run_gui() if options.gui else application.run()
    except OmegaError as error:
        print(f"Omega initialization failed: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
