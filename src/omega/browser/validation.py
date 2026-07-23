"""Central URL validation and privacy-safe URL redaction."""

from __future__ import annotations

import ipaddress
import re
from dataclasses import dataclass
from urllib.parse import SplitResult, urlsplit, urlunsplit

from omega.browser.configuration import BrowserConfiguration
from omega.browser.exceptions import UnsafeUrlError

_CONTROL = re.compile(r"[\x00-\x1f\x7f]")
_METADATA_HOSTS = frozenset(
    {
        "metadata",
        "metadata.google.internal",
        "instance-data",
        "instance-data.ec2.internal",
    }
)
_METADATA_IPS = frozenset({"169.254.169.254", "169.254.170.2", "100.100.100.200"})
_INTERNAL_SUFFIXES = (".localhost", ".local", ".internal")


@dataclass(frozen=True)
class ValidatedUrl:
    """Canonical URL and separately safe audit representation."""

    url: str
    host: str
    redacted_url: str


class UrlValidator:
    """Fail-closed validator for initial and redirected navigation URLs."""

    def __init__(self, configuration: BrowserConfiguration) -> None:
        self.configuration = configuration

    def validate(self, value: str) -> ValidatedUrl:
        if not isinstance(value, str) or not value.strip():
            raise UnsafeUrlError("A non-empty URL is required.")
        candidate = value.strip()
        if len(candidate) > self.configuration.maximum_url_characters:
            raise UnsafeUrlError("The URL exceeds Omega's safe length limit.")
        if _CONTROL.search(candidate):
            raise UnsafeUrlError("URLs must not contain control characters.")
        if "\\" in candidate:
            raise UnsafeUrlError("Backslashes are not accepted in browser URLs.")
        try:
            parsed = urlsplit(candidate)
            port = parsed.port
        except ValueError as error:
            raise UnsafeUrlError("The URL contains an invalid host or port.") from error
        scheme = parsed.scheme.casefold()
        if scheme not in self.configuration.allowed_schemes:
            raise UnsafeUrlError("That URL scheme is not permitted.")
        if scheme == "http" and not self.configuration.allow_http:
            raise UnsafeUrlError("Unencrypted HTTP navigation is disabled.")
        if not parsed.netloc or parsed.hostname is None:
            raise UnsafeUrlError("Web navigation requires a valid host.")
        if parsed.username is not None or parsed.password is not None:
            raise UnsafeUrlError("URLs containing credentials are prohibited.")
        host = self._normalize_host(parsed.hostname)
        self._validate_network_boundary(host)
        netloc = self._netloc(host, port)
        canonical = urlunsplit(
            SplitResult(
                scheme, netloc, parsed.path or "/", parsed.query, parsed.fragment
            )
        )
        redacted = urlunsplit(SplitResult(scheme, netloc, parsed.path or "/", "", ""))
        return ValidatedUrl(canonical, host, redacted)

    @staticmethod
    def _normalize_host(host: str) -> str:
        stripped = host.rstrip(".").casefold()
        if not stripped:
            raise UnsafeUrlError("Web navigation requires a valid host.")
        try:
            normalized = stripped.encode("idna").decode("ascii")
        except UnicodeError as error:
            raise UnsafeUrlError(
                "The internationalized host name is invalid."
            ) from error
        try:
            address = ipaddress.ip_address(normalized)
        except ValueError:
            address = None
        if address is not None:
            return normalized
        if len(normalized) > 253 or any(
            not label
            or len(label) > 63
            or label.startswith("-")
            or label.endswith("-")
            or re.fullmatch(r"[a-z0-9-]+", label) is None
            for label in normalized.split(".")
        ):
            raise UnsafeUrlError("The host name is malformed.")
        return normalized

    def _validate_network_boundary(self, host: str) -> None:
        if host in _METADATA_HOSTS or host in _METADATA_IPS:
            raise UnsafeUrlError("Cloud metadata endpoints are prohibited.")
        if not self.configuration.allow_localhost and (
            host == "localhost" or host.endswith(_INTERNAL_SUFFIXES) or "." not in host
        ):
            raise UnsafeUrlError("Local host names are disabled.")
        try:
            address = ipaddress.ip_address(host)
        except ValueError:
            return
        if str(address) in _METADATA_IPS:
            raise UnsafeUrlError("Cloud metadata endpoints are prohibited.")
        if address.is_loopback and not self.configuration.allow_localhost:
            raise UnsafeUrlError("Loopback addresses are disabled.")
        if (
            address.is_private
            or address.is_link_local
            or address.is_reserved
            or address.is_unspecified
            or address.is_multicast
        ) and not self.configuration.allow_private_networks:
            raise UnsafeUrlError(
                "Private and non-public network addresses are disabled."
            )

    @staticmethod
    def _netloc(host: str, port: int | None) -> str:
        display_host = f"[{host}]" if ":" in host else host
        return f"{display_host}:{port}" if port is not None else display_host


def redact_url(value: str) -> str:
    """Remove URL credentials, query parameters, and fragments for audit."""

    try:
        parsed = urlsplit(value)
        if not parsed.scheme or not parsed.hostname:
            return "[redacted-url]"
        host = parsed.hostname.encode("idna").decode("ascii")
        netloc = f"[{host}]" if ":" in host else host
        if parsed.port is not None:
            netloc = f"{netloc}:{parsed.port}"
        return urlunsplit(
            (parsed.scheme.casefold(), netloc, parsed.path or "/", "", "")
        )
    except (UnicodeError, ValueError):
        return "[redacted-url]"
