from pathlib import Path

import pytest

from omega.core.exceptions import VoiceConfigurationError
from omega.voice.configuration import VoiceConfiguration


def configuration(
    values: dict[str, object] | None = None,
) -> VoiceConfiguration:
    return VoiceConfiguration.from_mapping(
        values or {},
        wake_phrase="Hello Omega",
        shutdown_phrase="Shut down Omega",
        model_root=Path.cwd() / "data" / "voice_models",
    )


def test_safe_defaults_are_disabled_and_offline() -> None:
    result = configuration()

    assert result.enabled is False
    assert result.offline_recognition_enabled is True
    assert result.model_path is None
    assert result.sample_rate_hz == 16_000
    assert result.minimum_confidence == 0.5
    assert result.confirmation_confidence_threshold == 0.85


def test_relative_model_path_is_contained_in_model_root() -> None:
    result = configuration({"model_path": "english-small"})

    assert (
        result.model_path
        == (Path.cwd() / "data" / "voice_models" / "english-small").resolve()
    )


@pytest.mark.parametrize(
    "values, message",
    [
        ({"unknown": True}, "Unknown voice setting"),
        ({"enabled": 1}, "must be a boolean"),
        ({"offline_recognition_enabled": "yes"}, "must be a boolean"),
        ({"sample_rate_hz": True}, "must be an integer"),
        ({"sample_rate_hz": 7_999}, "between 8000 and 96000"),
        ({"sample_rate_hz": 96_001}, "between 8000 and 96000"),
        ({"audio_block_size": 100}, "between 256 and 65536"),
        ({"passive_listening_timeout_seconds": 0}, "between 0.05 and 60.0"),
        ({"active_listening_timeout_seconds": 121}, "between 0.1 and 120.0"),
        ({"active_session_timeout_seconds": -1}, "between 1.0 and 86400.0"),
        ({"maximum_transcript_characters": 0}, "between 1 and 10000"),
        ({"minimum_confidence": -0.1}, "between 0.0 and 1.0"),
        ({"minimum_confidence": True}, "between 0.0 and 1.0"),
        ({"confirmation_confidence_threshold": 1.1}, "between 0.0 and 1.0"),
        (
            {
                "minimum_confidence": 0.9,
                "confirmation_confidence_threshold": 0.8,
            },
            "must be at least",
        ),
        ({"speech_rate": 79}, "between 80 and 400"),
        ({"speech_volume": 1.1}, "between 0.0 and 1.0"),
        ({"microphone_device": -1}, "must be non-negative"),
        ({"microphone_device": []}, "integer, string, or null"),
        ({"model_path": "../outside"}, "must remain within"),
        ({"model_path": str(Path.cwd())}, "must remain within"),
    ],
)
def test_invalid_voice_settings_fail_closed(
    values: dict[str, object],
    message: str,
) -> None:
    with pytest.raises(VoiceConfigurationError, match=message):
        configuration(values)


def test_phrases_must_be_present_and_different() -> None:
    root = Path.cwd() / "data" / "voice_models"
    with pytest.raises(VoiceConfigurationError, match="non-empty"):
        VoiceConfiguration.from_mapping(
            {},
            wake_phrase=" ",
            shutdown_phrase="Stop",
            model_root=root,
        )
    with pytest.raises(VoiceConfigurationError, match="must be different"):
        VoiceConfiguration.from_mapping(
            {},
            wake_phrase="Hello Omega",
            shutdown_phrase=" hello   omega ",
            model_root=root,
        )
