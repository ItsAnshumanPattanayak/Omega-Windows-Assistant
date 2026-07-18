from types import MappingProxyType

import pytest

from omega.applications import ApplicationDefinition
from omega.core.exceptions import ApplicationRegistryError


def _definition(**overrides: object) -> ApplicationDefinition:
    values: dict[str, object] = {
        "application_id": "sample",
        "display_name": "Sample App",
        "aliases": ("sample", "sample app"),
        "executable_names": ("sample.exe",),
        "candidate_paths": (r"%WINDIR%\sample.exe",),
        "process_names": ("sample.exe",),
    }
    values.update(overrides)
    return ApplicationDefinition(**values)  # type: ignore[arg-type]


def test_valid_definition_is_immutable_and_serializable() -> None:
    definition = _definition(metadata={"category": "test"})

    assert definition.application_id == "sample"
    assert definition.aliases == ("sample", "sample app")
    assert isinstance(definition.metadata, MappingProxyType)
    assert definition.to_dict()["process_names"] == ["sample.exe"]
    with pytest.raises(TypeError):
        definition.metadata["changed"] = True  # type: ignore[index]


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("application_id", "Not Safe"),
        ("display_name", " "),
        ("aliases", ("same", "SAME")),
        ("executable_names", ("sample.exe & bad.exe",)),
        ("executable_names", ("cmd.exe /c bad",)),
        ("process_names", (r"..\sample.exe",)),
        ("candidate_paths", (r"%WINDIR%\..\sample.exe",)),
        ("uri", "https://example.com"),
    ],
)
def test_unsafe_definition_values_are_rejected(field: str, value: object) -> None:
    with pytest.raises(ApplicationRegistryError):
        _definition(**{field: value})


def test_definition_requires_a_controlled_target_and_independent_metadata() -> None:
    with pytest.raises(ApplicationRegistryError):
        _definition(executable_names=(), candidate_paths=(), uri=None)
    first = _definition()
    second = _definition(application_id="second", aliases=("second",))
    assert first.metadata is not second.metadata
