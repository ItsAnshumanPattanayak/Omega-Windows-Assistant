"""Public privacy-first personalization API."""

from omega.personalization.configuration import PersonalizationConfiguration
from omega.personalization.definitions import DEFINITION_MAP, DEFINITIONS, SAFETY_VALUES
from omega.personalization.exceptions import (
    PersonalizationDisabledError,
    PersonalizationError,
    PreferencePermissionError,
    PreferenceValidationError,
    ProfileError,
    ProfileTransferError,
)
from omega.personalization.integrations import (
    PersonalizationContext,
    PluginPreferenceAccess,
    WorkflowPreferenceAccess,
)
from omega.personalization.models import (
    PreferenceCategory,
    PreferenceChangeResult,
    PreferenceDefinition,
    PreferenceEvent,
    PreferenceScope,
    PreferenceSource,
    PreferenceValidationResult,
    ProfileImportPreview,
    ResolvedPreference,
    UserPreference,
    UserProfile,
)
from omega.personalization.repository import (
    FakePreferenceRepository,
    PreferenceRepository,
    SqlitePreferenceRepository,
)
from omega.personalization.resolver import PreferenceResolver
from omega.personalization.service import PreferenceService
from omega.personalization.transfer import (
    PROFILE_SCHEMA_VERSION,
    ProfileExportService,
    ProfileImportService,
)
from omega.personalization.validation import PreferenceValidator

__all__ = [
    "DEFINITIONS",
    "DEFINITION_MAP",
    "PROFILE_SCHEMA_VERSION",
    "SAFETY_VALUES",
    "FakePreferenceRepository",
    "PersonalizationConfiguration",
    "PersonalizationContext",
    "PersonalizationDisabledError",
    "PersonalizationError",
    "PluginPreferenceAccess",
    "PreferenceCategory",
    "PreferenceChangeResult",
    "PreferenceDefinition",
    "PreferenceEvent",
    "PreferencePermissionError",
    "PreferenceRepository",
    "PreferenceResolver",
    "PreferenceScope",
    "PreferenceService",
    "PreferenceSource",
    "PreferenceValidationError",
    "PreferenceValidationResult",
    "PreferenceValidator",
    "ProfileError",
    "ProfileExportService",
    "ProfileImportPreview",
    "ProfileImportService",
    "ProfileTransferError",
    "ResolvedPreference",
    "SqlitePreferenceRepository",
    "UserPreference",
    "UserProfile",
    "WorkflowPreferenceAccess",
]
