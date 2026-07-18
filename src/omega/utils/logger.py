"""Structured logging configuration for Omega."""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

LOG_FORMAT = "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def _parse_level(level: str) -> int:
    numeric_level = logging.getLevelName(level.upper())
    return numeric_level if isinstance(numeric_level, int) else logging.INFO


def _has_handler(logger: logging.Logger, handler_name: str) -> bool:
    return any(handler.get_name() == handler_name for handler in logger.handlers)


def configure_logging(
    *,
    level: str = "INFO",
    console_enabled: bool = True,
    file_enabled: bool = True,
    log_directory: Path | None = None,
    max_file_size_mb: int = 5,
    backup_count: int = 3,
) -> logging.Logger:
    """Configure the Omega logger once and return it.

    File logging is optional. If it cannot be initialized, startup continues with
    the remaining configured output handlers.
    """
    logger = logging.getLogger("omega")
    logger.setLevel(_parse_level(level))
    logger.propagate = False
    formatter = logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT)

    if console_enabled and not _has_handler(logger, "omega-console"):
        console_handler = logging.StreamHandler()
        console_handler.set_name("omega-console")
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

    if (
        file_enabled
        and log_directory is not None
        and not _has_handler(logger, "omega-file")
    ):
        try:
            log_directory.mkdir(parents=True, exist_ok=True)
            file_handler = RotatingFileHandler(
                log_directory / "omega.log",
                maxBytes=max_file_size_mb * 1024 * 1024,
                backupCount=backup_count,
                encoding="utf-8",
            )
            file_handler.set_name("omega-file")
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)
        except OSError:
            logger.warning(
                "File logging could not be initialized; continuing without it."
            )

    return logger


def get_logger(name: str) -> logging.Logger:
    """Return a named Omega logger without adding duplicate handlers."""
    return logging.getLogger(f"omega.{name}")
