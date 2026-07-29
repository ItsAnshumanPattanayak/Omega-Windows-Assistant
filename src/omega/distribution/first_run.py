"""Idempotent first-run preparation for a frozen Omega installation."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from omega.core.exceptions import DistributionError
from omega.utils.constants import APP_CONFIG_FILENAME
from omega.utils.paths import (
    config_dir,
    data_dir,
    ensure_runtime_directories,
    user_config_path,
)

_MAXIMUM_DEFAULT_CONFIG_BYTES = 512_000


@dataclass(frozen=True, slots=True)
class FirstRunResult:
    data_directory: Path
    configuration_path: Path
    configuration_created: bool


def ensure_user_configuration(
    *,
    default_path: Path | None = None,
    destination: Path | None = None,
) -> tuple[Path, bool]:
    """Copy safe defaults once without replacing an existing user file."""

    source = default_path or config_dir() / APP_CONFIG_FILENAME
    target = destination or user_config_path()
    if target.exists():
        return target, False
    try:
        payload = source.read_bytes()
    except OSError as error:
        raise DistributionError(
            "Packaged default configuration is unavailable."
        ) from error
    if not payload or len(payload) > _MAXIMUM_DEFAULT_CONFIG_BYTES:
        raise DistributionError("Packaged default configuration is invalid.")
    target.parent.mkdir(parents=True, exist_ok=True)
    descriptor: int | None = None
    try:
        descriptor = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "wb") as stream:
            descriptor = None
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
    except FileExistsError:
        return target, False
    except OSError as error:
        if descriptor is not None:
            os.close(descriptor)
        raise DistributionError(
            "User configuration could not be initialized."
        ) from error
    return target, True


def prepare_first_run(
    *,
    default_config_path: Path | None = None,
    destination: Path | None = None,
) -> FirstRunResult:
    """Create only Omega-owned runtime directories and a missing config file."""

    ensure_runtime_directories()
    path, created = ensure_user_configuration(
        default_path=default_config_path,
        destination=destination,
    )
    return FirstRunResult(data_dir(), path, created)
