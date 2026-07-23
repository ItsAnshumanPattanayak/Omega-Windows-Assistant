"""Strict browser configuration tests."""

import pytest

from omega.browser import BrowserConfiguration, BrowserConfigurationError
from omega.config.settings import load_settings
from omega.core.exceptions import SettingsRepositoryError
from omega.database import (
    DatabaseConfiguration,
    DatabaseConnectionFactory,
    MigrationRunner,
    RuntimeSettingsRepository,
)


def test_defaults_are_safe_and_browser_is_optional() -> None:
    config = BrowserConfiguration.from_mapping({})
    assert config.allowed_schemes == ("https",)
    assert not config.allow_downloads
    assert not config.allow_form_submission
    assert not config.allow_sensitive_input
    assert config.maximum_open_tabs == 10


@pytest.mark.parametrize(
    "values",
    [
        {"unknown": True},
        {"enabled": 1},
        {"maximum_open_tabs": True},
        {"maximum_open_tabs": 0},
        {"maximum_open_tabs": 26},
        {"preferred_browser": "opera"},
        {"default_search_engine": "custom"},
        {"allowed_schemes": ["http"]},
        {"allowed_schemes": ["https", "javascript"]},
        {"allowed_schemes": "https"},
    ],
)
def test_invalid_configuration_fails_closed(values: dict[str, object]) -> None:
    with pytest.raises(BrowserConfigurationError):
        BrowserConfiguration.from_mapping(values)


@pytest.mark.parametrize(
    "setting",
    [
        "allow_file_urls",
        "allow_url_credentials",
        "allow_javascript_urls",
        "allow_data_urls",
        "allow_downloads",
        "allow_form_submission",
        "allow_sensitive_input",
        "allow_private_mode",
    ],
)
def test_permanent_restrictions_cannot_be_enabled(setting: str) -> None:
    with pytest.raises(BrowserConfigurationError, match="cannot be enabled"):
        BrowserConfiguration.from_mapping({setting: True})


def test_explicit_http_requires_both_policy_values() -> None:
    config = BrowserConfiguration.from_mapping(
        {"allow_http": True, "allowed_schemes": ["https", "http"]}
    )
    assert config.allowed_schemes == ("https", "http")


def test_application_settings_supply_safe_browser_defaults(tmp_path) -> None:
    config = tmp_path / "app_config.yaml"
    config.write_text(
        "\n".join(
            [
                "application: {}",
                "user: {}",
                "assistant: {}",
                "logging: {}",
                "database: {}",
                "safety: {}",
                "applications: {}",
                "files: {}",
                "folders: {}",
                "recovery: {}",
                "history: {}",
            ]
        ),
        encoding="utf-8",
    )
    settings = load_settings(config)
    assert settings.browser_configuration == BrowserConfiguration()


def test_runtime_settings_cannot_weaken_browser_boundaries(tmp_path) -> None:
    factory = DatabaseConnectionFactory(
        DatabaseConfiguration(), database_path=tmp_path / "omega.db"
    )
    MigrationRunner(factory).migrate()
    repository = RuntimeSettingsRepository(factory)
    with pytest.raises(SettingsRepositoryError, match="immutable"):
        repository.upsert("browser.allow_downloads", True)
