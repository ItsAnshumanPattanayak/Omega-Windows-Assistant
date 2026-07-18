import json
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from omega.applications import ApplicationDefinition, ApplicationRegistry
from omega.core.exceptions import ApplicationRegistryError


def _definition(
    application_id: str = "sample", alias: str = "sample", *, enabled: bool = True
) -> ApplicationDefinition:
    return ApplicationDefinition(
        application_id=application_id,
        display_name=application_id.title(),
        aliases=(alias,),
        executable_names=(f"{application_id}.exe",),
        process_names=(f"{application_id}.exe",),
        enabled=enabled,
    )


def test_registry_resolves_ids_and_aliases_case_insensitively() -> None:
    registry = ApplicationRegistry([_definition(alias="Sample App")])

    assert registry.get("sample") is not None
    assert registry.resolve("  SAMPLE APP ") is registry.get("sample")
    assert registry.resolve("unknown") is None
    assert isinstance(registry.definitions, tuple)


def test_disabled_applications_are_excluded_by_default() -> None:
    registry = ApplicationRegistry([_definition(enabled=False)])

    assert registry.get("sample") is None
    assert registry.get("sample", include_disabled=True) is not None


def test_duplicate_ids_conflicting_aliases_and_empty_registry_are_rejected() -> None:
    with pytest.raises(ApplicationRegistryError, match="Duplicate application ID"):
        ApplicationRegistry([_definition(), _definition()])
    with pytest.raises(ApplicationRegistryError, match="Conflicting"):
        ApplicationRegistry([_definition(), _definition("other", "sample")])
    with pytest.raises(ApplicationRegistryError, match="must not be empty"):
        ApplicationRegistry([])


def test_registry_loads_canonical_configuration_and_rejects_invalid_json() -> None:
    registry = ApplicationRegistry.from_file()
    assert registry.get("chrome").display_name == "Google Chrome"  # type: ignore[union-attr]
    with TemporaryDirectory(dir=Path.cwd() / "data") as directory:
        path = Path(directory) / "bad.json"
        path.write_text(json.dumps({"applications": {"bad": []}}), encoding="utf-8")
        with pytest.raises(ApplicationRegistryError):
            ApplicationRegistry.from_file(path)
