"""Minimal application bootstrap for the Omega Phase 0 foundation."""

from __future__ import annotations

import sys
from collections.abc import Callable
from pathlib import Path

from omega.config.settings import Settings, load_settings
from omega.core.exceptions import InitializationError, UnsupportedPlatformError
from omega.interfaces.terminal import TerminalInterface
from omega.session.session import OmegaSession
from omega.utils.constants import MINIMUM_PYTHON_VERSION
from omega.utils.logger import configure_logging, get_logger
from omega.utils.paths import log_dir


class OmegaApplication:
    """Initialize Phase 0 without accepting or executing commands."""

    def __init__(self, config_path: Path | None = None) -> None:
        self.settings: Settings = load_settings(config_path)
        logging_settings = self.settings.logging
        self.logger = configure_logging(
            level=str(logging_settings["level"]),
            console_enabled=bool(logging_settings["console_enabled"]),
            file_enabled=bool(logging_settings["file_enabled"]),
            log_directory=log_dir(),
            max_file_size_mb=int(logging_settings["max_file_size_mb"]),
            backup_count=int(logging_settings["backup_count"]),
        )
        self._validate_python_version()
        self.logger = get_logger("app")
        self.session = OmegaSession(
            self.settings.user,
            self.settings.assistant,
            logger=get_logger("session"),
        )
        self.logger.info(
            "%s %s initialized in %s mode.",
            self.settings.application_name,
            self.settings.application_version,
            self.settings.application.get("environment", "development"),
        )

    @staticmethod
    def _validate_python_version() -> None:
        if sys.version_info < MINIMUM_PYTHON_VERSION:
            required = ".".join(str(value) for value in MINIMUM_PYTHON_VERSION)
            raise UnsupportedPlatformError(
                f"Omega requires Python {required} or newer."
            )

    def run(
        self,
        *,
        input_func: Callable[[str], str] = input,
        output_func: Callable[[str], None] = print,
    ) -> int:
        """Run the Phase 2 terminal session without executing user commands."""
        try:
            self.logger.info("Omega project foundation initialized successfully.")
            return TerminalInterface(
                self.session, input_func=input_func, output_func=output_func
            ).run()
        except OSError as error:
            raise InitializationError(
                "Omega could not complete startup logging."
            ) from error
