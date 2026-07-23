"""Application bootstrap for Omega's controlled text-session services."""

from __future__ import annotations

import sys
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

from omega.applications import (
    ApplicationManager,
    ApplicationOperationSettings,
    ApplicationProcessService,
    ApplicationRegistry,
    WindowsApplicationDiscovery,
    WindowsApplicationLauncher,
)
from omega.browser import (
    BrowserManager,
    PlaywrightBrowserBackend,
    UrlValidator,
)
from omega.config.settings import Settings, load_settings
from omega.core.exceptions import (
    DatabaseError,
    InitializationError,
    UnsupportedPlatformError,
)
from omega.database import (
    ActionRepository,
    CommandRepository,
    DatabaseConnectionFactory,
    ExecutionPersistence,
    MigrationRunner,
    RuntimeSettingsRepository,
    SqliteRecoveryRecordStore,
)
from omega.execution import (
    ApplicationActionDispatcher,
    BrowserActionDispatcher,
    FileActionDispatcher,
    FolderActionDispatcher,
    HistoryActionDispatcher,
    SystemActionDispatcher,
)
from omega.files import (
    FileLocationResolver,
    FileManager,
    FileOperationSettings,
    FileOperationsService,
    FilePathValidator,
    FileSearchService,
    SafeFilePathResolver,
    TextFileReader,
    TextFileWriter,
    WindowsFileOpener,
)
from omega.folders import (
    FolderCreator,
    FolderInspector,
    FolderManager,
    FolderOperations,
    FolderOperationSettings,
    FolderPathValidator,
    FolderSearch,
    WindowsFolderOpener,
)
from omega.history import HistoryService
from omega.interfaces.terminal import TerminalInterface
from omega.recovery import (
    RecoveryConfiguration,
    RecoveryRegistry,
    WindowsRecycleBinService,
)
from omega.safety import (
    ConfirmationManager,
    PermissionConfiguration,
    PermissionPolicyEngine,
    ProtectedResourceEvaluator,
    SafeExecutionGateway,
)
from omega.session.session import OmegaSession
from omega.system import (
    PsutilSystemInformationProvider,
    SystemManager,
    UnavailableAudioController,
    UnavailableBrightnessController,
    WindowsPowerController,
    WindowsSettingsPageLauncher,
)
from omega.utils.constants import MINIMUM_PYTHON_VERSION
from omega.utils.logger import configure_logging, get_logger
from omega.utils.paths import log_dir
from omega.voice.models import AudioDevice
from omega.voice.protocols import VoiceEventSink

if TYPE_CHECKING:
    from omega.voice.service import VoiceService


class OmegaApplication:
    """Initialize configuration, logging, and controlled application services."""

    def __init__(
        self,
        config_path: Path | None = None,
        *,
        database_path: Path | None = None,
    ) -> None:
        self.started_at = datetime.now(UTC)
        self.settings: Settings = load_settings(config_path)
        logging_settings = self.settings.logging
        self.logger = configure_logging(
            level=str(logging_settings["level"]),
            console_enabled=bool(logging_settings["console_enabled"]),
            file_enabled=bool(logging_settings["file_enabled"]),
            log_directory=log_dir(),
            max_file_size_mb=int(logging_settings["max_file_size_mb"]),
            backup_count=int(logging_settings["backup_count"]),
        )
        self._validate_python_version()
        self.logger = get_logger("app")

        protected_resources = ProtectedResourceEvaluator.from_file()

        try:
            database_factory = DatabaseConnectionFactory(
                self.settings.database_configuration,
                database_path=database_path,
            )
            MigrationRunner(database_factory).migrate()
            command_repository = CommandRepository(database_factory)
            action_repository = ActionRepository(database_factory)
            runtime_settings_repository = RuntimeSettingsRepository(database_factory)
        except DatabaseError as error:
            raise InitializationError(
                "Omega could not initialize required local persistence."
            ) from error

        safety_gateway = SafeExecutionGateway(
            policy_engine=PermissionPolicyEngine(
                configuration=PermissionConfiguration.from_file(),
                protected_resources=protected_resources,
            ),
            confirmations=ConfirmationManager(
                timeout_seconds=float(
                    self.settings.safety["confirmation_timeout_seconds"]
                ),
                maximum_attempts=int(
                    self.settings.safety["maximum_confirmation_attempts"]
                ),
            ),
            logger=get_logger("safety.gateway"),
            persistence=ExecutionPersistence(
                command_repository,
                action_repository,
            ),
        )

        recovery_configuration = RecoveryConfiguration.from_mapping(
            self.settings.recovery
        )
        recovery_store = (
            SqliteRecoveryRecordStore(
                database_factory,
                recovery_configuration.maximum_undo_records,
            )
            if recovery_configuration.persist_undo_records
            else None
        )
        recovery_registry = RecoveryRegistry(
            recovery_configuration,
            store=recovery_store,
        )
        recycle_bin_service = WindowsRecycleBinService(
            recovery_configuration,
            protected_path_checker=lambda path: self._is_protected_path(
                protected_resources,
                path,
            ),
        )

        registry = ApplicationRegistry.from_file()
        application_manager = ApplicationManager(
            registry,
            WindowsApplicationDiscovery(logger=get_logger("applications.discovery")),
            WindowsApplicationLauncher(logger=get_logger("applications.launcher")),
            ApplicationProcessService(logger=get_logger("applications.processes")),
            settings=ApplicationOperationSettings.from_mapping(
                self.settings.applications
            ),
            logger=get_logger("applications.manager"),
        )

        file_settings = FileOperationSettings.from_mapping(self.settings.files)
        locations = FileLocationResolver(startup_directory=Path.cwd())
        file_manager = FileManager(
            locations,
            SafeFilePathResolver(
                locations,
                FilePathValidator(),
            ),
            TextFileReader(
                file_settings.maximum_read_size_bytes,
                file_settings.maximum_display_characters,
            ),
            TextFileWriter(
                file_settings.maximum_write_size_bytes,
                file_settings.maximum_resulting_file_size_bytes,
            ),
            FileOperationsService(),
            FileSearchService(
                file_settings.search_max_depth,
                file_settings.search_max_results,
            ),
            WindowsFileOpener(),
            settings=file_settings,
            recycle_bin_service=recycle_bin_service,
            recovery_registry=recovery_registry,
            logger=get_logger("files.manager"),
        )

        folder_settings = FolderOperationSettings.from_mapping(self.settings.folders)
        folder_validator = FolderPathValidator()
        folder_inspector = FolderInspector(folder_validator)
        folder_manager = FolderManager(
            locations,
            folder_validator,
            FolderCreator(),
            folder_inspector,
            FolderOperations(
                folder_inspector,
                folder_validator,
            ),
            FolderSearch(folder_validator),
            WindowsFolderOpener(),
            settings=folder_settings,
            recycle_bin_service=recycle_bin_service,
            recovery_registry=recovery_registry,
            logger=get_logger("folders.manager"),
        )

        self.recovery_configuration = recovery_configuration
        self.recovery_registry = recovery_registry
        self.recycle_bin_service = recycle_bin_service
        self.database_factory = database_factory
        self.command_repository = command_repository
        self.action_repository = action_repository
        self.runtime_settings_repository = runtime_settings_repository
        self.safety_gateway = safety_gateway
        self.history_service = HistoryService(
            database_factory,
            command_repository,
            action_repository,
            recovery_registry.store,
            default_limit=int(self.settings.history["default_limit"]),
            maximum_limit=int(self.settings.history["maximum_limit"]),
            maximum_export_bytes=int(self.settings.history["maximum_export_bytes"]),
            export_root=(
                database_path.parent / "history_exports"
                if database_path is not None
                else None
            ),
        )
        browser_configuration = self.settings.browser_configuration
        browser_validator = UrlValidator(browser_configuration)
        self.browser_manager = BrowserManager(
            browser_configuration,
            PlaywrightBrowserBackend(browser_validator),
            validator=browser_validator,
        )
        system_manager = SystemManager(
            self.settings.system_configuration,
            PsutilSystemInformationProvider(),
            UnavailableAudioController(),
            UnavailableBrightnessController(),
            WindowsSettingsPageLauncher(),
            WindowsPowerController(),
        )

        self.session = OmegaSession(
            self.settings.user,
            self.settings.assistant,
            logger=get_logger("session"),
            application_dispatcher=ApplicationActionDispatcher(
                application_manager,
                registry,
                gateway=safety_gateway,
            ),
            file_dispatcher=FileActionDispatcher(
                file_manager,
                gateway=safety_gateway,
            ),
            folder_dispatcher=FolderActionDispatcher(
                folder_manager,
                gateway=safety_gateway,
            ),
            history_dispatcher=HistoryActionDispatcher(
                self.history_service,
                safety_gateway,
            ),
            browser_dispatcher=BrowserActionDispatcher(
                self.browser_manager,
                safety_gateway,
                browser_validator,
            ),
            system_dispatcher=SystemActionDispatcher(
                system_manager,
                safety_gateway,
            ),
            safety_gateway=safety_gateway,
        )
        self.voice_configuration = self.settings.voice_configuration

        self.logger.info(
            "%s %s initialized in %s mode.",
            self.settings.application_name,
            self.settings.application_version,
            self.settings.application.get(
                "environment",
                "development",
            ),
        )

    @staticmethod
    def _is_protected_path(
        evaluator: ProtectedResourceEvaluator,
        path: Path,
    ) -> bool:
        resolved = path.resolve(strict=False)

        return any(
            evaluator._within(resolved, protected) for protected in evaluator._protected
        )

    @staticmethod
    def _validate_python_version() -> None:
        if sys.version_info < MINIMUM_PYTHON_VERSION:
            required = ".".join(str(value) for value in MINIMUM_PYTHON_VERSION)
            raise UnsupportedPlatformError(
                f"Omega requires Python {required} or newer."
            )

    def run(
        self,
        *,
        input_func: Callable[[str], str] = input,
        output_func: Callable[[str], None] = print,
    ) -> int:
        """Run the terminal session and return its process exit code."""

        try:
            self.logger.info("Omega project foundation initialized successfully.")
            return TerminalInterface(
                self.session,
                input_func=input_func,
                output_func=output_func,
            ).run()
        except OSError as error:
            raise InitializationError(
                "Omega could not complete startup logging."
            ) from error
        finally:
            self.browser_manager.shutdown()

    def run_gui(self) -> int:
        """Run the optional desktop presentation over this composition root."""

        from omega.gui.application import OmegaGuiApplication

        self.logger.info("Starting Omega's optional desktop interface.")
        return OmegaGuiApplication(self).run()

    def shutdown(self) -> None:
        """Release only resources explicitly owned by this Omega instance."""

        self.browser_manager.shutdown()

    def create_voice_service(
        self,
        *,
        event_sink: VoiceEventSink | None = None,
    ) -> VoiceService:
        """Explicitly create local audio adapters; never called by text startup."""

        from omega.core.exceptions import VoiceInitializationError
        from omega.voice.microphone import SoundDeviceMicrophone
        from omega.voice.recognizer import VoskSpeechRecognizer
        from omega.voice.service import VoiceService
        from omega.voice.speaker import SapiSpeechSynthesizer

        configuration = self.voice_configuration
        if not configuration.enabled:
            raise VoiceInitializationError(
                "Voice is disabled. Set voice.enabled to true in "
                "config/app_config.yaml."
            )
        if not configuration.offline_recognition_enabled:
            raise VoiceInitializationError(
                "Offline recognition must be enabled for Phase 12 voice mode."
            )
        microphone = SoundDeviceMicrophone(
            device=configuration.microphone_device,
            sample_rate_hz=configuration.sample_rate_hz,
            block_size=configuration.audio_block_size,
        )
        recognizer = VoskSpeechRecognizer(
            configuration.model_path,
            sample_rate_hz=configuration.sample_rate_hz,
            maximum_characters=configuration.maximum_transcript_characters,
        )
        speaker = (
            SapiSpeechSynthesizer(
                rate=configuration.speech_rate,
                volume=configuration.speech_volume,
                voice_name=configuration.voice_name,
            )
            if configuration.speak_responses
            else None
        )
        return VoiceService(
            configuration,
            self.session,
            self.safety_gateway,
            microphone,
            recognizer,
            speaker,
            event_sink=event_sink,
            logger=get_logger("voice"),
        )

    def run_voice(
        self,
        *,
        output_func: Callable[[str], None] = print,
    ) -> int:
        """Run explicit terminal voice mode with safe text-only fallback."""

        from omega.voice.terminal import VoiceTerminalInterface

        try:
            return VoiceTerminalInterface(
                lambda sink: self.create_voice_service(event_sink=sink),
                output_func=output_func,
            ).run()
        finally:
            self.browser_manager.shutdown()

    def list_audio_devices(self) -> tuple[AudioDevice, ...]:
        """Enumerate bounded safe microphone metadata on explicit request."""

        from omega.voice.microphone import SoundDeviceMicrophone

        configuration = self.voice_configuration
        return SoundDeviceMicrophone(
            device=configuration.microphone_device,
            sample_rate_hz=configuration.sample_rate_hz,
            block_size=configuration.audio_block_size,
        ).list_devices()
