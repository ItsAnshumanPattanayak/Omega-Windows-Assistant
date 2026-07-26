"""Conservative, credential-free email configuration."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from omega.email.exceptions import EmailConfigurationError


@dataclass(frozen=True)
class EmailConfiguration:
    """Validated policy limits; authentication values are deliberately absent."""

    enabled: bool = False
    provider: str | None = None
    account_name: str | None = None
    maximum_messages_per_request: int = 20
    maximum_search_query_characters: int = 300
    maximum_body_characters: int = 20_000
    maximum_summary_characters: int = 1_500
    maximum_recipients: int = 10
    maximum_subject_characters: int = 300
    maximum_draft_body_characters: int = 50_000
    provider_timeout_seconds: float = 20.0
    allow_attachment_downloads: bool = False
    maximum_attachment_bytes: int = 10_485_760
    require_confirmation_for_send: bool = True
    require_confirmation_for_archive: bool = True

    def __post_init__(self) -> None:
        self._validate()

    @classmethod
    def from_mapping(cls, values: Mapping[str, Any]) -> EmailConfiguration:
        """Validate an exact configuration mapping without resolving secrets."""
        allowed = set(cls.__dataclass_fields__)
        unknown = set(values).difference(allowed)
        if unknown:
            raise EmailConfigurationError(
                "Unknown email setting(s): " + ", ".join(sorted(unknown))
            )
        try:
            value = cls(**values)
        except TypeError as error:
            raise EmailConfigurationError("Email configuration is invalid.") from error
        return value

    def _validate(self) -> None:
        for name in (
            "enabled",
            "allow_attachment_downloads",
            "require_confirmation_for_send",
            "require_confirmation_for_archive",
        ):
            if not isinstance(getattr(self, name), bool):
                raise EmailConfigurationError(f"email.{name} must be a boolean.")
        if self.enabled and (not self.provider or not self.provider.strip()):
            raise EmailConfigurationError(
                "email.provider is required when email is enabled."
            )
        if self.provider is not None and self.provider not in {"fake"}:
            raise EmailConfigurationError(
                "email.provider must be null or an explicitly supported provider."
            )
        if self.account_name is not None and (
            not self.account_name.strip() or len(self.account_name) > 120
        ):
            raise EmailConfigurationError(
                "email.account_name must contain 1 to 120 characters."
            )
        bounds = {
            "maximum_messages_per_request": (1, 100),
            "maximum_search_query_characters": (1, 2_000),
            "maximum_body_characters": (1, 200_000),
            "maximum_summary_characters": (100, 10_000),
            "maximum_recipients": (1, 50),
            "maximum_subject_characters": (1, 998),
            "maximum_draft_body_characters": (1, 500_000),
            "maximum_attachment_bytes": (1, 100_000_000),
        }
        for name, (minimum, maximum) in bounds.items():
            item = getattr(self, name)
            if (
                isinstance(item, bool)
                or not isinstance(item, int)
                or not minimum <= item <= maximum
            ):
                raise EmailConfigurationError(
                    f"email.{name} must be between {minimum} and {maximum}."
                )
        timeout = self.provider_timeout_seconds
        if (
            isinstance(timeout, bool)
            or not isinstance(timeout, (int, float))
            or not 1 <= timeout <= 120
        ):
            raise EmailConfigurationError(
                "email.provider_timeout_seconds must be between 1 and 120."
            )
        if self.allow_attachment_downloads:
            raise EmailConfigurationError(
                "Attachment downloads are unavailable in Phase 18 and must remain "
                "disabled."
            )
        if (
            not self.require_confirmation_for_send
            or not self.require_confirmation_for_archive
        ):
            raise EmailConfigurationError(
                "Email send and archive confirmations must remain enabled."
            )
