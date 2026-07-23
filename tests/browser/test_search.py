"""Trusted search URL construction tests."""

import pytest

from omega.browser import BrowserConfiguration, BrowserNavigationError, UrlValidator
from omega.browser.search import build_search_url


@pytest.mark.parametrize(
    ("engine", "host"),
    [
        ("duckduckgo", "duckduckgo.com"),
        ("bing", "www.bing.com"),
        ("google", "www.google.com"),
    ],
)
def test_search_engines_use_trusted_encoded_templates(engine: str, host: str) -> None:
    config = BrowserConfiguration()
    result = build_search_url(
        "python decorators & typing", engine, config, UrlValidator(config)
    )
    assert result.host == host
    assert "python+decorators+%26+typing" in result.url


def test_invalid_engine_and_query_are_rejected() -> None:
    config = BrowserConfiguration()
    validator = UrlValidator(config)
    with pytest.raises(BrowserNavigationError):
        build_search_url("query", "custom", config, validator)
    with pytest.raises(BrowserNavigationError):
        build_search_url(" ", "duckduckgo", config, validator)


def test_search_query_limit_is_enforced() -> None:
    config = BrowserConfiguration(maximum_search_query_characters=10)
    with pytest.raises(BrowserNavigationError, match="limit"):
        build_search_url("x" * 11, "duckduckgo", config, UrlValidator(config))
