"""Strict browser policy configuration with immutable safety boundaries."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from omega.browser.exceptions import BrowserConfigurationError

_BROWSERS = frozenset({"chromium", "edge", "chrome", "firefox"})
_SEARCH_ENGINES = frozenset({"duckduckgo", "bing", "google"})
_SAFE_SCHEMES = frozenset({"https", "http"})
_DANGEROUS_SCHEMES = frozenset(
    {
        "about",
        "chrome",
        "command",
        "data",
        "devtools",
        "edge",
        "file",
        "javascript",
        "powershell",
        "shell",
        "vbscript",
        "view-source",
    }
)


@dataclass(frozen=True)
class BrowserConfiguration:
    """Validated browser preferences; prohibited capabilities stay disabled."""

    enabled: bool = True
    preferred_browser: str = "edge"
    automation_enabled: bool = True
    allowed_schemes: tuple[str, ...] = ("https",)
    allow_http: bool = False
    allow_file_urls: bool = False
    allow_localhost: bool = False
    allow_private_networks: bool = False
    allow_url_credentials: bool = False
    allow_javascript_urls: bool = False
    allow_data_urls: bool = False
    allow_downloads: bool = False
    allow_form_submission: bool = False
    allow_sensitive_input: bool = False
    allow_private_mode: bool = False
    navigation_timeout_seconds: int = 20
    operation_timeout_seconds: int = 10
    maximum_open_tabs: int = 10
    maximum_url_characters: int = 2048
    maximum_page_title_characters: int = 300
    maximum_page_text_characters: int = 10_000
    maximum_search_query_characters: int = 500
    maximum_bookmark_name_characters: int = 100
    default_search_engine: str = "duckduckgo"

    @classmethod
    def from_mapping(cls, values: Mapping[str, Any]) -> BrowserConfiguration:
        """Reject unknown keys, coercion, and attempts to weaken hard policy."""

        allowed = set(cls.__dataclass_fields__)
        unknown = set(values).difference(allowed)
        if unknown:
            raise BrowserConfigurationError(
                "Unknown browser setting(s): " + ", ".join(sorted(unknown))
            )
        defaults = cls()
        merged = {
            name: values.get(name, getattr(defaults, name))
            for name in cls.__dataclass_fields__
        }
        boolean_names = (
            "enabled",
            "automation_enabled",
            "allow_http",
            "allow_file_urls",
            "allow_localhost",
            "allow_private_networks",
            "allow_url_credentials",
            "allow_javascript_urls",
            "allow_data_urls",
            "allow_downloads",
            "allow_form_submission",
            "allow_sensitive_input",
            "allow_private_mode",
        )
        for name in boolean_names:
            if not isinstance(merged[name], bool):
                raise BrowserConfigurationError(f"browser.{name} must be a boolean.")
        permanently_disabled = (
            "allow_file_urls",
            "allow_url_credentials",
            "allow_javascript_urls",
            "allow_data_urls",
            "allow_downloads",
            "allow_form_submission",
            "allow_sensitive_input",
            "allow_private_mode",
        )
        if any(merged[name] is not False for name in permanently_disabled):
            raise BrowserConfigurationError(
                "Prohibited browser capabilities cannot be enabled."
            )
        browser = merged["preferred_browser"]
        if not isinstance(browser, str) or browser.casefold() not in _BROWSERS:
            raise BrowserConfigurationError("browser.preferred_browser is unsupported.")
        search_engine = merged["default_search_engine"]
        if (
            not isinstance(search_engine, str)
            or search_engine.casefold() not in _SEARCH_ENGINES
        ):
            raise BrowserConfigurationError(
                "browser.default_search_engine is unsupported."
            )
        schemes = merged["allowed_schemes"]
        if not isinstance(schemes, (list, tuple)) or not schemes:
            raise BrowserConfigurationError(
                "browser.allowed_schemes must be a non-empty list."
            )
        normalized_schemes: list[str] = []
        for scheme in schemes:
            if not isinstance(scheme, str):
                raise BrowserConfigurationError(
                    "browser.allowed_schemes must contain strings."
                )
            normalized = scheme.casefold()
            if normalized in _DANGEROUS_SCHEMES or normalized not in _SAFE_SCHEMES:
                raise BrowserConfigurationError(
                    f"Browser scheme {normalized!r} is prohibited."
                )
            if normalized == "http" and merged["allow_http"] is not True:
                raise BrowserConfigurationError(
                    "HTTP may be listed only when browser.allow_http is true."
                )
            if normalized not in normalized_schemes:
                normalized_schemes.append(normalized)
        if "https" not in normalized_schemes:
            raise BrowserConfigurationError("HTTPS must remain enabled.")
        bounds = {
            "navigation_timeout_seconds": (1, 120),
            "operation_timeout_seconds": (1, 60),
            "maximum_open_tabs": (1, 25),
            "maximum_url_characters": (128, 8192),
            "maximum_page_title_characters": (1, 1000),
            "maximum_page_text_characters": (1, 50_000),
            "maximum_search_query_characters": (1, 2000),
            "maximum_bookmark_name_characters": (1, 300),
        }
        for name, (minimum, maximum) in bounds.items():
            value = merged[name]
            if (
                isinstance(value, bool)
                or not isinstance(value, int)
                or not minimum <= value <= maximum
            ):
                raise BrowserConfigurationError(
                    f"browser.{name} must be between {minimum} and {maximum}."
                )
        merged["preferred_browser"] = browser.casefold()
        merged["default_search_engine"] = search_engine.casefold()
        merged["allowed_schemes"] = tuple(normalized_schemes)
        return cls(**merged)
