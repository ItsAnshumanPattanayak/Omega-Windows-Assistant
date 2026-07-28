from __future__ import annotations

import json
from datetime import datetime, time
from uuid import uuid4

import pytest

from omega.personalization import (
    PersonalizationConfiguration,
    PersonalizationContext,
    PluginPreferenceAccess,
    PreferencePermissionError,
    PreferenceService,
    ProfileExportService,
    ProfileImportService,
    ProfileTransferError,
    WorkflowPreferenceAccess,
)


def test_export_contains_schema_and_excludes_private_content(
    service: PreferenceService, configuration: PersonalizationConfiguration
) -> None:
    service.set_preference("display_name", "Anshuman")
    exported = ProfileExportService(service, configuration).export_json()
    value = json.loads(exported)
    assert value["schema_version"] == 1
    assert value["privacy"]["contains_credentials"] is False
    lowered = exported.casefold()
    assert "password" not in lowered
    assert "token" not in lowered
    assert "clipboard" not in lowered


def test_import_requires_preview_and_confirmation(
    service: PreferenceService, configuration: PersonalizationConfiguration
) -> None:
    importer = ProfileImportService(service, configuration)
    preview = importer.preview(
        json.dumps(
            {
                "schema_version": 1,
                "profile": {"name": "Imported"},
                "preferences": {"response_verbosity": "concise"},
                "privacy": {},
            }
        )
    )
    assert "validated preference" in preview.summary()
    with pytest.raises(ProfileTransferError, match="confirmation"):
        importer.apply(preview.preview_id)
    second = importer.preview(
        json.dumps(
            {
                "schema_version": 1,
                "profile": {"name": "Imported"},
                "preferences": {"response_verbosity": "concise"},
            }
        )
    )
    assert importer.apply(second.preview_id, confirmed=True) == 1
    assert service.resolver.resolve("response_verbosity").value == "concise"


@pytest.mark.parametrize(
    "payload",
    [
        "not json",
        json.dumps({"schema_version": 99, "profile": {}, "preferences": {}}),
        json.dumps(
            {
                "schema_version": 1,
                "profile": {"name": "X"},
                "preferences": {"password": "secret"},
            }
        ),
        json.dumps(
            {
                "schema_version": 1,
                "profile": {"name": "X"},
                "preferences": {"display_name": "exec(bad)"},
            }
        ),
        json.dumps(
            {
                "schema_version": 1,
                "profile": {"name": "X"},
                "preferences": {},
                "critical_unknown": True,
            }
        ),
    ],
)
def test_invalid_imports_are_rejected(
    service: PreferenceService,
    configuration: PersonalizationConfiguration,
    payload: str,
) -> None:
    with pytest.raises(ProfileTransferError):
        ProfileImportService(service, configuration).preview(payload)


def test_oversized_import_is_rejected(service: PreferenceService) -> None:
    configuration = PersonalizationConfiguration(maximum_export_bytes=1024)
    with pytest.raises(ProfileTransferError, match="too large"):
        ProfileImportService(service, configuration).preview(b"x" * 1025)


def test_workflow_access_is_allowlisted_and_revalidated(
    service: PreferenceService,
) -> None:
    access = WorkflowPreferenceAccess(service.resolver, service)
    service.set_preference("default_browser", "chrome")
    assert access.resolve("default_browser") == "chrome"
    with pytest.raises(PreferencePermissionError):
        access.resolve("display_name")


def test_plugin_read_permission_and_namespace_isolation(
    service: PreferenceService,
) -> None:
    fingerprint = "a" * 64
    approvals = {("example", "1.0.0", fingerprint, "read_non_sensitive_preferences")}

    def check(
        plugin_id: str, version: str, fingerprint_value: str, permission: str
    ) -> None:
        if (plugin_id, version, fingerprint_value, permission) not in approvals:
            raise PreferencePermissionError("denied")

    access = PluginPreferenceAccess(service.resolver, check)
    service.set_preference("language", "en")
    assert access.read("example", "1.0.0", fingerprint, "language") == "en"
    with pytest.raises(PreferencePermissionError):
        access.read("other", "1.0.0", fingerprint, "language")
    with pytest.raises(PreferencePermissionError):
        access.read("example", "1.0.0", fingerprint, "display_name")
    approvals.add(("example", "1.0.0", fingerprint, "write_plugin_preferences"))
    access.write_own("example", "1.0.0", fingerprint, "example.theme", "dark")
    with pytest.raises(PreferencePermissionError):
        access.write_own("example", "1.0.0", fingerprint, "other.theme", "dark")
    with pytest.raises(PreferencePermissionError):
        access.read("example", "1.0.1", fingerprint, "language")


def test_ai_context_is_minimal(service: PreferenceService) -> None:
    service.set_preference("language", "en")
    service.set_preference("display_name", "Secret Name")
    context = PersonalizationContext(service.resolver).for_ai("language")
    assert context == {"language": "en"}
    assert "display_name" not in context


def test_response_formatting_preserves_safety_details(
    service: PreferenceService,
) -> None:
    session_id = uuid4()
    service.set_preference(
        "response_verbosity", "concise", session_id=session_id, temporary=True
    )
    context = PersonalizationContext(service.resolver)
    warning = "Safety warning.\nDo not suppress this confirmation detail."
    assert (
        context.format_response(warning, session_id=session_id, safety_critical=True)
        == warning
    )
    assert context.format_response(warning, session_id=session_id) == "Safety warning."


def test_detailed_response_is_deterministic(service: PreferenceService) -> None:
    service.set_preference("response_verbosity", "detailed")
    value = PersonalizationContext(service.resolver).format_response("Result")
    assert value.startswith("Result")
    assert "underlying result" in value


def test_greeting_uses_explicit_name_and_style(service: PreferenceService) -> None:
    service.set_preference("display_name", "Anshuman")
    service.set_preference("greeting_style", "brief")
    greeting = PersonalizationContext(service.resolver).greeting(
        "Fallback", datetime(2026, 1, 1, 9, 0)
    )
    assert greeting == "Good morning, Anshuman."


def test_quiet_and_working_hours_are_deterministic(service: PreferenceService) -> None:
    service.set_preference("quiet_hours", "22:00-07:00")
    service.set_preference("working_hours", "09:00-17:00")
    context = PersonalizationContext(service.resolver)
    assert context.is_quiet_time(time(23, 0))
    assert context.is_quiet_time(time(6, 59))
    assert not context.is_quiet_time(time(7, 0))
    assert context.is_working_time(time(10, 0))
    assert not context.is_working_time(time(18, 0))
