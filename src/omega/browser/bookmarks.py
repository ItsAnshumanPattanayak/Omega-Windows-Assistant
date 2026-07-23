"""Process-local Omega bookmark store with validated deterministic behavior."""

from __future__ import annotations

from threading import RLock

from omega.browser.configuration import BrowserConfiguration
from omega.browser.exceptions import BrowserError
from omega.browser.models import Bookmark
from omega.browser.validation import UrlValidator


class BookmarkStore:
    """Store Omega-managed bookmarks without touching browser-native databases."""

    def __init__(
        self,
        configuration: BrowserConfiguration,
        validator: UrlValidator,
    ) -> None:
        self.configuration = configuration
        self.validator = validator
        self._items: dict[str, Bookmark] = {}
        self._lock = RLock()

    def save(self, name: str, url: str) -> Bookmark:
        cleaned_name = " ".join(name.split())
        if not cleaned_name:
            raise BrowserError("A bookmark name is required.")
        if len(cleaned_name) > self.configuration.maximum_bookmark_name_characters:
            raise BrowserError("The bookmark name exceeds Omega's safe limit.")
        key = cleaned_name.casefold()
        validated = self.validator.validate(url)
        with self._lock:
            if key in self._items:
                raise BrowserError("A bookmark with that name already exists.")
            bookmark = Bookmark(cleaned_name, validated.url)
            self._items[key] = bookmark
            return bookmark

    def get(self, name: str) -> Bookmark | None:
        with self._lock:
            return self._items.get(" ".join(name.split()).casefold())

    def list(self) -> tuple[Bookmark, ...]:
        with self._lock:
            return tuple(
                sorted(self._items.values(), key=lambda item: item.name.casefold())
            )
