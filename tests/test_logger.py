"""Tests for reusable structured logging."""

import logging
from pathlib import Path
from tempfile import TemporaryDirectory

from omega.utils.logger import configure_logging, get_logger


def _reset_omega_handlers() -> None:
    logger = logging.getLogger("omega")
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
        handler.close()


def test_logger_initialization_creates_console_and_rotating_file_handlers() -> None:
    with TemporaryDirectory(dir=Path.cwd() / "data") as temporary_directory:
        _reset_omega_handlers()

        temp_path = Path(temporary_directory)
        logger = configure_logging(log_directory=temp_path)
        logger.info("test message")

        handler_names = {handler.get_name() for handler in logger.handlers}
        assert {"omega-console", "omega-file"}.issubset(handler_names)
        assert (temp_path / "omega.log").exists()

        _reset_omega_handlers()


def test_configure_logging_does_not_duplicate_handlers() -> None:
    with TemporaryDirectory(dir=Path.cwd() / "data") as temporary_directory:
        _reset_omega_handlers()

        temp_path = Path(temporary_directory)
        first = configure_logging(log_directory=temp_path)
        second = configure_logging(log_directory=temp_path)

        assert first is second
        assert len(second.handlers) == 2
        assert get_logger("tests").name == "omega.tests"

        _reset_omega_handlers()
