"""Trusted search-engine URL construction."""

from urllib.parse import urlencode

from omega.browser.configuration import BrowserConfiguration
from omega.browser.exceptions import BrowserNavigationError
from omega.browser.validation import UrlValidator, ValidatedUrl

_SEARCH_ENDPOINTS = {
    "duckduckgo": "https://duckduckgo.com/",
    "bing": "https://www.bing.com/search",
    "google": "https://www.google.com/search",
}


def build_search_url(
    query: str,
    engine: str,
    configuration: BrowserConfiguration,
    validator: UrlValidator,
) -> ValidatedUrl:
    """Encode one bounded query into an allowlisted immutable URL template."""

    cleaned = query.strip()
    if not cleaned:
        raise BrowserNavigationError("A non-empty search query is required.")
    if len(cleaned) > configuration.maximum_search_query_characters:
        raise BrowserNavigationError("The search query exceeds Omega's safe limit.")
    normalized_engine = engine.casefold()
    endpoint = _SEARCH_ENDPOINTS.get(normalized_engine)
    if endpoint is None:
        raise BrowserNavigationError("That search engine is not approved.")
    return validator.validate(f"{endpoint}?{urlencode({'q': cleaned})}")
