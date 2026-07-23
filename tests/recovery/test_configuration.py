"""Tests for recovery configuration validation."""

import pytest

from omega.core.exceptions import ConfigurationError
from omega.recovery import RecoveryConfiguration


def valid_configuration_values() -> dict[str, object]:
    """Return a valid explicit recovery configuration."""

    return {
        "enabled": True,
        "allow_permanent_deletion": False,
        "require_confirmation_for_recycle": True,
        "require_confirmation_for_restore": True,
        "undo_timeout_seconds": 300,
        "maximum_undo_records": 20,
        "maximum_recycle_size_bytes": 1_024,
        "persist_undo_records": False,
    }


def test_default_recovery_configuration_is_safe() -> None:
    configuration = RecoveryConfiguration()

    assert configuration.enabled is True
    assert configuration.allow_permanent_deletion is False
    assert configuration.require_confirmation_for_recycle is True
    assert configuration.require_confirmation_for_restore is True
    assert configuration.persist_undo_records is False
    assert configuration.maximum_undo_records == 20


def test_configuration_loads_from_mapping() -> None:
    values = valid_configuration_values()
    values["undo_timeout_seconds"] = 120
    values["maximum_undo_records"] = 10

    configuration = RecoveryConfiguration.from_mapping(values)

    assert configuration.undo_timeout_seconds == 120
    assert configuration.maximum_undo_records == 10
    assert configuration.maximum_recycle_size_bytes == 1_024


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        (
            {"allow_permanent_deletion": True},
            "does not permit permanent deletion",
        ),
        (
            {"undo_timeout_seconds": 0},
            "undo_timeout_seconds",
        ),
        (
            {"maximum_undo_records": 0},
            "maximum_undo_records",
        ),
        (
            {"maximum_recycle_size_bytes": 0},
            "maximum_recycle_size_bytes",
        ),
    ],
)
def test_unsafe_or_invalid_configuration_is_rejected(
    overrides: dict[str, object],
    message: str,
) -> None:
    values = valid_configuration_values()
    values.update(overrides)

    with pytest.raises(ConfigurationError, match=message):
        RecoveryConfiguration.from_mapping(values)


def test_unknown_configuration_field_is_rejected() -> None:
    values = valid_configuration_values()
    values["unknown_switch"] = True

    with pytest.raises(ConfigurationError, match="Unknown recovery"):
        RecoveryConfiguration.from_mapping(values)


def test_persistent_recovery_can_be_enabled_strictly() -> None:
    values = valid_configuration_values()
    values["persist_undo_records"] = True

    assert RecoveryConfiguration.from_mapping(values).persist_undo_records is True


def test_non_mapping_configuration_is_rejected() -> None:
    with pytest.raises(ConfigurationError, match="must be a mapping"):
        RecoveryConfiguration.from_mapping([])  # type: ignore[arg-type]
