"""Adversarial URL-boundary tests."""

import pytest

from omega.browser import BrowserConfiguration, UnsafeUrlError, UrlValidator, redact_url


@pytest.fixture
def validator() -> UrlValidator:
    return UrlValidator(BrowserConfiguration())


def test_valid_https_url_is_canonical_and_redacted(validator: UrlValidator) -> None:
    result = validator.validate(" HTTPS://ExAmPle.COM/path?q=secret#fragment ")
    assert result.url == "https://example.com/path?q=secret#fragment"
    assert result.host == "example.com"
    assert result.redacted_url == "https://example.com/path"


def test_idn_host_is_normalized(validator: UrlValidator) -> None:
    result = validator.validate("https://bücher.example/")
    assert result.host == "xn--bcher-kva.example"


@pytest.mark.parametrize(
    "url",
    [
        "javascript:alert(1)",
        "data:text/plain,hello",
        "file:///C:/Windows/system.ini",
        "about:blank",
        "chrome://settings",
        "edge://settings",
        "devtools://devtools",
        "view-source:https://example.com",
        "https://user:password@example.com/",
        "https://localhost/",
        "https://service.local/",
        "https://127.0.0.1/",
        "https://[::1]/",
        "https://10.0.0.1/",
        "https://172.16.0.1/",
        "https://192.168.1.1/",
        "https://169.254.1.1/",
        "https://169.254.169.254/latest/meta-data/",
        "https://metadata.google.internal/",
        "https://0.0.0.0/",
        "https://224.0.0.1/",
        "https://example.com:99999/",
        "https://example.com\\@evil.test/",
        "https://exa_mple.com/",
        "https:///missing-host",
        "https://example.com/\x00value",
        "https://example.com/\nvalue",
        "http://example.com/",
    ],
)
def test_unsafe_urls_are_rejected(validator: UrlValidator, url: str) -> None:
    with pytest.raises(UnsafeUrlError):
        validator.validate(url)


def test_url_length_is_bounded() -> None:
    validator = UrlValidator(BrowserConfiguration(maximum_url_characters=128))
    with pytest.raises(UnsafeUrlError, match="length"):
        validator.validate("https://example.com/" + "a" * 200)


def test_redaction_never_returns_credentials_or_query() -> None:
    value = redact_url("https://user:secret@example.com/path?token=abc#private")
    assert value == "https://example.com/path"
    assert "secret" not in value
    assert "token" not in value


def test_trusted_policy_can_allow_public_http() -> None:
    config = BrowserConfiguration.from_mapping(
        {"allow_http": True, "allowed_schemes": ["https", "http"]}
    )
    assert (
        UrlValidator(config).validate("http://example.com/").url.startswith("http://")
    )
