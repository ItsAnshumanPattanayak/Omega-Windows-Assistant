from __future__ import annotations

from uuid import uuid4

from omega.system import (
    AudioState,
    BatterySummary,
    BrightnessState,
    CpuSummary,
    DiskSummary,
    MemorySummary,
    NetworkSummary,
    PowerActionRequest,
    PowerOperation,
    ProcessSummary,
    SystemConfiguration,
    SystemManager,
    SystemSummary,
)


class FakeInformation:
    def system_summary(self) -> SystemSummary:
        return SystemSummary(
            "Windows", "AMD64", 20, self.cpu_summary(), self.memory_summary()
        )

    def cpu_summary(self) -> CpuSummary:
        return CpuSummary(8, 4, 25.0)

    def memory_summary(self) -> MemorySummary:
        return MemorySummary(100, 50, 50, 50.0)

    def disk_summaries(self, limit: int) -> tuple[DiskSummary, ...]:
        return (DiskSummary("C:", 100, 50, 50, 50.0),)[:limit]

    def battery_summary(self) -> BatterySummary:
        return BatterySummary(False)

    def network_summary(self, limit: int) -> NetworkSummary:
        return NetworkSummary(True, min(limit, 1), 10, 20, ("Ethernet",))

    def processes(
        self, limit: int, name: str | None = None
    ) -> tuple[ProcessSummary, ...]:
        values = (ProcessSummary(10, "notepad.exe", 0.0, 1.0, "running"),)
        return tuple(item for item in values if name is None or name in item.name)[
            :limit
        ]


class FakeAudio:
    def __init__(self) -> None:
        self.state = AudioState(50, False)

    def get_state(self) -> AudioState:
        return self.state

    def set_volume(self, percent: int) -> AudioState:
        self.state = AudioState(percent, self.state.muted)
        return self.state

    def set_muted(self, muted: bool) -> AudioState:
        self.state = AudioState(self.state.volume_percent, muted)
        return self.state


class FakeBrightness:
    def __init__(self) -> None:
        self.state = BrightnessState((50,))

    def get_state(self) -> BrightnessState:
        return self.state

    def set_brightness(self, percent: int) -> BrightnessState:
        self.state = BrightnessState((percent,))
        return self.state


class FakeSettings:
    def __init__(self) -> None:
        self.opened: list[str] = []

    def open_page(self, page: str) -> None:
        self.opened.append(page)


class FakePower:
    def __init__(self) -> None:
        self.requests: list[PowerActionRequest] = []

    def execute(self, request: PowerActionRequest) -> None:
        self.requests.append(request)


def manager() -> tuple[SystemManager, FakeAudio, FakeBrightness, FakePower]:
    audio, brightness, power = FakeAudio(), FakeBrightness(), FakePower()
    return (
        SystemManager(
            SystemConfiguration(),
            FakeInformation(),
            audio,
            brightness,
            FakeSettings(),
            power,
        ),
        audio,
        brightness,
        power,
    )


def test_information_is_bounded_and_redacted() -> None:
    value, _, _, _ = manager()
    result = value.information_result(uuid4(), uuid4(), "process", "notepad")
    assert result.success
    process = result.data["processes"][0]  # type: ignore[index]
    assert process["name"] == "notepad.exe"  # type: ignore[index]
    assert "command_line" not in process
    assert "environment" not in process


def test_audio_and_brightness_apply_safe_bounds() -> None:
    value, audio, brightness, _ = manager()
    assert value.audio_result(uuid4(), uuid4(), "increase", 10).success
    assert audio.state.volume_percent == 60
    assert value.audio_result(uuid4(), uuid4(), "set", 101).success is False
    brightness.state = BrightnessState((20,))
    assert value.brightness_result(uuid4(), uuid4(), "decrease", 25).success
    assert brightness.state.percentages == (10,)


def test_power_adapter_is_called_once() -> None:
    value, _, _, power = manager()
    result = value.power_result(uuid4(), uuid4(), PowerOperation.RESTART)
    assert result.success
    assert len(power.requests) == 1
    assert power.requests[0].countdown_seconds == 10
