"""Windows distribution metadata, first-run behavior, and verification."""

from omega.distribution.entrypoint import selected_arguments
from omega.distribution.first_run import (
    FirstRunResult,
    ensure_user_configuration,
    prepare_first_run,
)
from omega.distribution.metadata import APPLICATION_METADATA, ApplicationMetadata
from omega.distribution.verification import (
    DistributionVerification,
    require_safe_distribution,
    verify_distribution,
)

__all__ = [
    "APPLICATION_METADATA",
    "ApplicationMetadata",
    "DistributionVerification",
    "FirstRunResult",
    "ensure_user_configuration",
    "prepare_first_run",
    "require_safe_distribution",
    "selected_arguments",
    "verify_distribution",
]
