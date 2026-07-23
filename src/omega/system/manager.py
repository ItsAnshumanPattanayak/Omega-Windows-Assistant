"""Validated system operations with typed results and no parsing logic."""

from __future__ import annotations

from uuid import UUID

from omega.models import ActionResult, ErrorCategory, OmegaErrorDetails
from omega.system.configuration import SystemConfiguration
from omega.system.models import PowerActionRequest, PowerOperation
from omega.system.protocols import (
    AudioController,
    BrightnessController,
    PowerController,
    SettingsPageLauncher,
    SystemInformationProvider,
)


class SystemManager:
    """Apply configuration bounds and invoke one injected adapter exactly once."""

    def __init__(
        self,
        configuration: SystemConfiguration,
        information: SystemInformationProvider,
        audio: AudioController,
        brightness: BrightnessController,
        settings_pages: SettingsPageLauncher,
        power: PowerController,
    ) -> None:
        self.configuration = configuration
        self.information = information
        self.audio = audio
        self.brightness = brightness
        self.settings_pages = settings_pages
        self.power = power

    def information_result(
        self, action_id: UUID, command_id: UUID, category: str, query: str | None = None
    ) -> ActionResult:
        try:
            if (
                not self.configuration.enabled
                or not self.configuration.information_enabled
            ):
                raise RuntimeError("System information is disabled.")
            if category == "system":
                data = self.information.system_summary().to_dict()
                message = "System information is ready."
            elif category == "cpu":
                data = self.information.cpu_summary().to_dict()
                message = f"CPU usage is {data['usage_percent']:.1f}%."
            elif category == "memory":
                data = self.information.memory_summary().to_dict()
                message = f"Memory usage is {data['usage_percent']:.1f}%."
            elif category == "disk":
                values = self.information.disk_summaries(
                    self.configuration.maximum_disk_results
                )
                data = {"disks": [item.to_dict() for item in values]}
                message = f"Found {len(values)} fixed disk volume(s)."
            elif category == "battery":
                battery = self.information.battery_summary()
                data = battery.to_dict()
                message = (
                    f"Battery is at {battery.percent:.0f}%."
                    if battery.available and battery.percent is not None
                    else "Battery information is unavailable on this device."
                )
            elif category == "network":
                network = self.information.network_summary(
                    self.configuration.maximum_network_results
                )
                data = network.to_dict()
                message = (
                    "A network interface is connected."
                    if network.connected
                    else "No connected network interface was found."
                )
            elif category == "process":
                if not self.configuration.process_listing_enabled:
                    raise RuntimeError("Process listing is disabled.")
                processes = self.information.processes(
                    self.configuration.maximum_process_results, query
                )
                data = {"processes": [item.to_dict() for item in processes]}
                message = f"Found {len(processes)} matching process(es)."
            else:
                raise ValueError("Unknown information category.")
            return ActionResult.success_result(
                action_id, message, message, data=data, metadata={"category": category}
            )
        except Exception as error:
            return self._failure(
                action_id, command_id, "SYSTEM_INFORMATION_FAILED", error
            )

    def audio_result(
        self,
        action_id: UUID,
        command_id: UUID,
        operation: str,
        percent: int | None = None,
    ) -> ActionResult:
        try:
            if (
                not self.configuration.enabled
                or not self.configuration.audio_control_enabled
            ):
                raise RuntimeError("Audio control is disabled.")
            state = self.audio.get_state()
            if operation == "get":
                updated = state
            elif operation == "set":
                updated = self.audio.set_volume(self._volume(percent))
            elif operation in {"increase", "decrease"}:
                increment = self._increment(percent)
                target = state.volume_percent + (
                    increment if operation == "increase" else -increment
                )
                updated = self.audio.set_volume(self._volume(target, clamp=True))
            elif operation == "mute":
                updated = self.audio.set_muted(True)
            elif operation == "unmute":
                updated = self.audio.set_muted(False)
            else:
                raise ValueError("Unknown audio operation.")
            message = (
                f"Volume is {updated.volume_percent}%"
                f"{' and muted' if updated.muted else ''}."
            )
            return ActionResult.success_result(
                action_id, message, message, data=updated.to_dict()
            )
        except Exception as error:
            return self._failure(action_id, command_id, "AUDIO_CONTROL_FAILED", error)

    def brightness_result(
        self,
        action_id: UUID,
        command_id: UUID,
        operation: str,
        percent: int | None = None,
    ) -> ActionResult:
        try:
            if (
                not self.configuration.enabled
                or not self.configuration.brightness_control_enabled
            ):
                raise RuntimeError("Brightness control is disabled.")
            state = self.brightness.get_state()
            if operation == "get":
                updated = state
            elif operation == "set":
                updated = self.brightness.set_brightness(self._brightness(percent))
            elif operation in {"increase", "decrease"}:
                increment = self._increment(percent)
                current = state.percentages[0]
                target = current + (
                    increment if operation == "increase" else -increment
                )
                updated = self.brightness.set_brightness(
                    self._brightness(target, clamp=True)
                )
            else:
                raise ValueError("Unknown brightness operation.")
            message = (
                "Brightness is "
                + ", ".join(f"{value}%" for value in updated.percentages)
                + "."
            )
            return ActionResult.success_result(
                action_id, message, message, data=updated.to_dict()
            )
        except Exception as error:
            return self._failure(
                action_id, command_id, "BRIGHTNESS_CONTROL_FAILED", error
            )

    def open_settings(
        self, action_id: UUID, command_id: UUID, page: str
    ) -> ActionResult:
        try:
            if (
                not self.configuration.enabled
                or not self.configuration.settings_pages_enabled
            ):
                raise RuntimeError("Windows Settings pages are disabled.")
            self.settings_pages.open_page(page)
            message = f"Opened the allowlisted {page.replace('_', ' ')} settings page."
            return ActionResult.success_result(
                action_id, message, message, data={"settings_page": page}
            )
        except Exception as error:
            return self._failure(action_id, command_id, "SETTINGS_PAGE_FAILED", error)

    def power_result(
        self, action_id: UUID, command_id: UUID, operation: PowerOperation
    ) -> ActionResult:
        try:
            if (
                not self.configuration.enabled
                or not self.configuration.power_actions_enabled
            ):
                raise RuntimeError("Power actions are disabled.")
            enabled = {
                PowerOperation.LOCK: self.configuration.lock_enabled,
                PowerOperation.SLEEP: self.configuration.sleep_enabled,
                PowerOperation.HIBERNATE: self.configuration.hibernate_enabled,
                PowerOperation.SIGN_OUT: self.configuration.sign_out_enabled,
                PowerOperation.RESTART: self.configuration.restart_enabled,
                PowerOperation.SHUTDOWN: self.configuration.shutdown_enabled,
                PowerOperation.CANCEL: self.configuration.allow_cancel_power_countdown,
            }[operation]
            if not enabled:
                raise RuntimeError(f"{operation.value} is disabled.")
            countdown = (
                self.configuration.power_countdown_seconds
                if operation in {PowerOperation.RESTART, PowerOperation.SHUTDOWN}
                else 0
            )
            self.power.execute(PowerActionRequest(operation, countdown))
            message = (
                "The pending Windows power countdown was cancelled."
                if operation is PowerOperation.CANCEL
                else (
                    "Windows accepted the "
                    f"{operation.value.replace('_', ' ')} request."
                )
            )
            return ActionResult.success_result(
                action_id,
                message,
                message,
                data={
                    "power_operation": operation.value,
                    "countdown_seconds": countdown,
                },
            )
        except Exception as error:
            return self._failure(action_id, command_id, "POWER_ACTION_FAILED", error)

    def _volume(self, value: int | None, *, clamp: bool = False) -> int:
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValueError("A whole-number volume percentage is required.")
        low, high = (
            self.configuration.minimum_volume_percent,
            self.configuration.maximum_volume_percent,
        )
        if clamp:
            return max(low, min(high, value))
        if not low <= value <= high:
            raise ValueError(f"Volume must be between {low} and {high} percent.")
        return value

    def _brightness(self, value: int | None, *, clamp: bool = False) -> int:
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValueError("A whole-number brightness percentage is required.")
        low, high = (
            self.configuration.minimum_brightness_percent,
            self.configuration.maximum_brightness_percent,
        )
        if clamp:
            return max(low, min(high, value))
        if not low <= value <= high:
            raise ValueError(f"Brightness must be between {low} and {high} percent.")
        return value

    def _increment(self, value: int | None) -> int:
        selected = 10 if value is None else value
        if (
            isinstance(selected, bool)
            or not isinstance(selected, int)
            or not 1 <= selected <= self.configuration.maximum_control_increment_percent
        ):
            raise ValueError("The requested increment is outside the safe range.")
        return selected

    @staticmethod
    def _failure(
        action_id: UUID, command_id: UUID, code: str, error: Exception
    ) -> ActionResult:
        user_message = str(error) or "That system feature is unavailable."
        details = OmegaErrorDetails(
            code=code,
            category=ErrorCategory.UNSUPPORTED,
            message=type(error).__name__,
            user_message=user_message,
            recoverable=True,
            action_id=action_id,
            command_id=command_id,
        )
        return ActionResult.failure_result(
            action_id, type(error).__name__, user_message, details
        )
