from __future__ import annotations

import json
from pathlib import Path

import pytest

from omega.accessibility import (
    LanguageIdentifier,
    LanguagePackDescriptor,
    LanguagePackValidator,
    LocaleIdentifier,
    LocalizationConfiguration,
    PluginLocalizationRegistry,
    create_default_localization,
)
from omega.core.exceptions import LanguagePackValidationError


def _descriptor(
    *, preview: bool = False, coverage: float = 1.0
) -> LanguagePackDescriptor:
    return LanguagePackDescriptor(
        "Test",
        LanguageIdentifier("hi"),
        LocaleIdentifier("hi_IN"),
        "1.0.0",
        coverage=coverage,
        preview=preview,
    )


def test_english_catalog_is_complete_and_fingerprinted() -> None:
    service = create_default_localization()
    catalog = service.registry.get("en")
    assert catalog is not None
    assert catalog.entries["app.ready"] == "Omega is ready."
    assert len(catalog.fingerprint()) == 64
    assert catalog.fingerprint() == catalog.fingerprint()


def test_hindi_is_explicitly_partial_preview() -> None:
    catalog = create_default_localization().registry.get("hi")
    assert catalog is not None
    assert catalog.descriptor.preview is True
    assert catalog.descriptor.coverage < 1.0
    assert catalog.descriptor.text_direction.value == "ltr"


def test_imported_partial_pack_respects_disabled_policy() -> None:
    with pytest.raises(LanguagePackValidationError):
        LanguagePackValidator(LocalizationConfiguration()).validate(
            _descriptor(preview=True, coverage=0.5), {"app.ready": "तैयार"}
        )


def test_translation_and_missing_fallback() -> None:
    service = create_default_localization()
    service.set_language("hi")
    assert service.message("app.ready").language.value == "hi"
    missing = service.message("knowledge.results")
    assert missing.text == "Knowledge search results"
    assert missing.used_fallback is True
    assert service.message("missing.diagnostic").text == "missing.diagnostic"


def test_critical_confirmation_uses_complete_english_catalog() -> None:
    service = create_default_localization()
    service.set_language("hi")
    message = service.message(
        "confirmation.destructive", action="Delete", target="report.txt"
    )
    assert message.language.value == "en"
    assert "destructive" in message.text


@pytest.mark.parametrize(
    "key,value",
    [
        ("bad", "value"),
        ("app.ready", ""),
        ("app.ready", "bad\x00text"),
        ("app.ready", "<script>alert(1)</script>"),
        ("app.ready", "eval(value)"),
        ("app.ready", object()),
    ],
)
def test_catalog_rejects_invalid_or_executable_content(key: str, value: object) -> None:
    with pytest.raises(LanguagePackValidationError):
        LanguagePackValidator(LocalizationConfiguration()).validate(
            _descriptor(), {key: value}
        )


@pytest.mark.parametrize(
    "translation",
    ["Hello", "Hello {wrong}", "Hello {name!r}", "Hello {name:>4}"],
)
def test_catalog_rejects_placeholder_mismatch(translation: str) -> None:
    validator = LanguagePackValidator(LocalizationConfiguration())
    base = validator.validate(_descriptor(), {"app.hello": "Hello {name}"})
    with pytest.raises(LanguagePackValidationError):
        validator.validate(_descriptor(), {"app.hello": translation}, base_catalog=base)


def test_catalog_rejects_oversized_entries_and_bytes() -> None:
    config = LocalizationConfiguration(
        maximum_catalog_bytes=1024, maximum_message_characters=10
    )
    validator = LanguagePackValidator(config)
    with pytest.raises(LanguagePackValidationError):
        validator.validate(_descriptor(), {"app.ready": "x" * 11})
    many = {f"app.key-{index}": "x" * 10 for index in range(100)}
    with pytest.raises(LanguagePackValidationError):
        validator.validate(_descriptor(), many)


def test_json_loader_is_bounded_and_rejects_traversal(tmp_path: Path) -> None:
    root = tmp_path / "packs"
    root.mkdir()
    catalog = root / "hi.json"
    catalog.write_text(json.dumps({"app.ready": "तैयार"}), encoding="utf-8")
    validator = LanguagePackValidator(LocalizationConfiguration())
    assert validator.load_json(catalog, _descriptor(), root=root).entries
    outside = tmp_path / "outside.json"
    outside.write_text("{}", encoding="utf-8")
    with pytest.raises(LanguagePackValidationError):
        validator.load_json(outside, _descriptor(), root=root)


def test_plugin_translation_namespace_and_permission_isolation() -> None:
    registry = PluginLocalizationRegistry(
        LanguagePackValidator(LocalizationConfiguration())
    )
    with pytest.raises(LanguagePackValidationError):
        registry.register(
            "weather",
            _descriptor(),
            {"plugin.weather.label": "मौसम"},
            permission_granted=False,
        )
    with pytest.raises(LanguagePackValidationError):
        registry.register(
            "weather",
            _descriptor(),
            {"confirmation.destructive": "unsafe"},
            permission_granted=True,
        )
    result = registry.register(
        "weather",
        _descriptor(),
        {"plugin.weather.label": "मौसम"},
        permission_granted=True,
    )
    assert result.entries["plugin.weather.label"] == "मौसम"


def test_missing_language_pack_is_rejected() -> None:
    service = create_default_localization()
    with pytest.raises(LanguagePackValidationError):
        service.set_language("fr")
