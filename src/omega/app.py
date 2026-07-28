"""Application bootstrap for Omega's controlled text-session services."""

from __future__ import annotations

import sys
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING
from uuid import UUID

from omega.accessibility import (
    AccessibilityService,
    LocaleFormatter,
    create_default_aliases,
    create_default_localization,
)
from omega.ai import (
    AiKnowledgeAssistant,
    AiModelCapability,
    AiModelDescriptor,
    AiModelRegistry,
    AiProposalService,
    AiProviderRegistry,
    AiResourceManager,
    AiService,
    LoopbackHttpAiProvider,
    PluginAiAccess,
)
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
from omega.calendar import FakeCalendarProvider, SqliteCalendarOperationStore
from omega.calendar.service import CalendarService
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
from omega.desktop_utilities import (
    ClipboardService,
    DesktopInformationService,
    PillowScreenshotBackend,
    ScreenshotService,
    TkClipboardBackend,
    TkScreenInformationProvider,
    WindowsPathOpener,
    WindowsWindowInformationProvider,
)
from omega.email import FakeEmailProvider, SqliteEmailOperationStore
from omega.email.service import EmailService
from omega.execution import (
    AiDispatcher,
    ApplicationActionDispatcher,
    BrowserActionDispatcher,
    CalendarActionDispatcher,
    DesktopUtilityActionDispatcher,
    EmailActionDispatcher,
    FileActionDispatcher,
    FolderActionDispatcher,
    HistoryActionDispatcher,
    KnowledgeActionDispatcher,
    PluginDispatcher,
    PreferenceDispatcher,
    ProductivityActionDispatcher,
    SchedulingActionDispatcher,
    SystemActionDispatcher,
    WorkflowDispatcher,
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
from omega.knowledge import (
    DeterministicChunker,
    KnowledgeRepository,
    KnowledgeService,
    KnowledgeSourceType,
)
from omega.knowledge.export_service import KnowledgeExportService
from omega.knowledge.extractors import (
    DocxExtractor,
    ExtractorRegistry,
    MarkdownExtractor,
    PdfExtractor,
    TextExtractor,
)
from omega.knowledge.semantic_search import UnavailableSemanticSearch
from omega.knowledge.validation import KnowledgeFileValidator
from omega.models._serialization import JsonValue
from omega.personalization import (
    PersonalizationContext,
    PluginPreferenceAccess,
    PreferenceResolver,
    PreferenceService,
    PreferenceValidator,
    ProfileExportService,
    ProfileImportService,
    SqlitePreferenceRepository,
    WorkflowPreferenceAccess,
)
from omega.plugins import (
    PluginDiscovery,
    PluginLifecycle,
    PluginLoader,
    PluginManager,
    PluginPackageInstaller,
    PluginPermission,
    PluginPermissionService,
    PluginRegistry,
    PluginRepository,
    PluginValidator,
)
from omega.productivity.export import ProductivityExportService
from omega.productivity.importers import ProductivityImportService
from omega.productivity.repositories import ProductivityRepository
from omega.productivity.service import ProductivityService
from omega.recovery import (
    RecoveryConfiguration,
    RecoveryRegistry,
    WindowsRecycleBinService,
)
from omega.recovery.windows_recycle_bin import WindowsShellRecycleBinBackend
from omega.safety import (
    ConfirmationManager,
    PermissionConfiguration,
    PermissionPolicyEngine,
    ProtectedResourceEvaluator,
    SafeExecutionGateway,
)
from omega.scheduling import (
    NotificationCenter,
    SchedulerEngine,
    ScheduleRepository,
    SchedulingService,
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
from omega.understanding.parser import CommandParser
from omega.utils.constants import MINIMUM_PYTHON_VERSION
from omega.utils.logger import configure_logging, get_logger
from omega.utils.paths import data_dir, log_dir
from omega.voice.models import AudioDevice
from omega.voice.protocols import VoiceEventSink
from omega.workflows import (
    WorkflowExecutor,
    WorkflowPlanner,
    WorkflowRepository,
    WorkflowRunRepository,
    WorkflowService,
    WorkflowStep,
    WorkflowStepType,
    WorkflowValidator,
)

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
        self.accessibility_service = AccessibilityService(
            self.settings.accessibility_configuration
        )
        logging_settings = self.settings.logging
        self.logger = configure_logging(
            level=str(logging_settings["level"]),
            console_enabled=bool(logging_settings["console_enabled"]),
            file_enabled=bool(logging_settings["file_enabled"]),
            log_directory=log_dir(),
            max_file_size_mb=int(logging_settings["max_file_size_mb"]),
            backup_count=int(logging_settings["backup_count"]),
            maximum_message_characters=(
                self.settings.security_configuration.maximum_log_message_characters
            ),
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
                timeout_seconds=self.accessibility_service.confirmation_timeout(
                    float(self.settings.safety["confirmation_timeout_seconds"])
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
        personalization_configuration = self.settings.personalization_configuration
        application_aliases = {
            alias
            for definition in registry.definitions
            for alias in (definition.application_id, *definition.aliases)
        }
        self.preference_repository = SqlitePreferenceRepository(database_factory)
        self.preference_resolver = PreferenceResolver(
            self.preference_repository,
            {
                "response_verbosity": (
                    personalization_configuration.default_response_verbosity
                ),
                "language": personalization_configuration.default_language,
                "time_format": personalization_configuration.default_time_format,
                "date_format": personalization_configuration.default_date_format,
                "unit_system": personalization_configuration.default_unit_system,
            },
        )
        self.preference_service = PreferenceService(
            personalization_configuration,
            self.preference_repository,
            PreferenceValidator(
                personalization_configuration,
                application_aliases=application_aliases,
            ),
            self.preference_resolver,
        )
        self.profile_export_service = ProfileExportService(
            self.preference_service, personalization_configuration
        )
        self.profile_import_service = ProfileImportService(
            self.preference_service, personalization_configuration
        )
        self.personalization_context = PersonalizationContext(self.preference_resolver)
        self.localization_service = create_default_localization(
            self.settings.localization_configuration
        )
        preferred_language = self.preference_resolver.resolve("language").value
        if isinstance(
            preferred_language, str
        ) and self.localization_service.registry.get(preferred_language):
            self.localization_service.set_language(preferred_language)
        preferred_locale = self.preference_resolver.resolve("locale").value
        self.locale_formatter = LocaleFormatter(
            str(preferred_locale),
            time_format=str(self.preference_resolver.resolve("time_format").value),
            date_format=str(self.preference_resolver.resolve("date_format").value),
            time_zone=str(self.preference_resolver.resolve("time_zone").value),
            unit_system=str(self.preference_resolver.resolve("unit_system").value),
        )
        self.workflow_preference_access = WorkflowPreferenceAccess(
            self.preference_resolver, self.preference_service
        )
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
        self.file_manager = file_manager

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
        scheduling_repository = ScheduleRepository(database_factory)
        scheduling_service = SchedulingService(
            self.settings.scheduling_configuration, scheduling_repository
        )
        productivity_repository = ProductivityRepository(database_factory)
        self.productivity_service = ProductivityService(
            self.settings.productivity_configuration,
            productivity_repository,
            scheduling_repository,
            scheduling_service,
        )
        productivity_root = (
            database_path.parent / "productivity"
            if database_path is not None
            else data_dir() / "productivity"
        )
        self.productivity_export_service = ProductivityExportService(
            self.settings.productivity_configuration,
            productivity_repository,
            productivity_root / "exports",
        )
        self.productivity_import_service = ProductivityImportService(
            self.settings.productivity_configuration,
            self.productivity_service,
            productivity_root / "imports",
        )
        knowledge_configuration = self.settings.knowledge_configuration
        knowledge_repository = KnowledgeRepository(database_factory)
        knowledge_root = (
            database_path.parent / "knowledge"
            if database_path is not None
            else data_dir() / "knowledge"
        )
        knowledge_validator = KnowledgeFileValidator(
            knowledge_configuration,
            (
                Path.cwd(),
                Path.home() / "Desktop",
                Path.home() / "Documents",
                Path.home() / "Downloads",
                knowledge_root / "imports",
            ),
        )
        knowledge_extractors = ExtractorRegistry(
            {
                KnowledgeSourceType.TEXT: TextExtractor(knowledge_configuration),
                KnowledgeSourceType.MARKDOWN: MarkdownExtractor(
                    knowledge_configuration
                ),
                KnowledgeSourceType.DOCX: DocxExtractor(knowledge_configuration),
                KnowledgeSourceType.PDF: PdfExtractor(knowledge_configuration),
            }
        )
        self.knowledge_service = KnowledgeService(
            knowledge_configuration,
            knowledge_repository,
            knowledge_validator,
            knowledge_extractors,
            DeterministicChunker(knowledge_configuration),
            UnavailableSemanticSearch(),
        )
        self.knowledge_export_service = KnowledgeExportService(
            knowledge_configuration,
            knowledge_repository,
            knowledge_root / "exports",
        )
        email_configuration = self.settings.email_configuration
        email_provider = (
            FakeEmailProvider()
            if email_configuration.enabled and email_configuration.provider == "fake"
            else None
        )
        self.email_service = EmailService(
            email_configuration,
            email_provider,
            SqliteEmailOperationStore(database_factory),
        )
        calendar_configuration = self.settings.calendar_configuration
        calendar_provider = (
            FakeCalendarProvider()
            if calendar_configuration.enabled
            and calendar_configuration.provider == "fake"
            else None
        )
        self.calendar_service = CalendarService(
            calendar_configuration,
            calendar_provider,
            SqliteCalendarOperationStore(database_factory),
        )
        desktop_configuration = self.settings.desktop_utilities_configuration
        self.clipboard_service = ClipboardService(
            desktop_configuration, TkClipboardBackend()
        )
        screenshot_root = (
            database_path.parent / "screenshots"
            if database_path is not None
            else data_dir() / "screenshots"
        )
        recycle_backend = WindowsShellRecycleBinBackend()

        def recycle_screenshot(path: Path) -> None:
            outcome = recycle_backend.recycle(path)
            if not outcome.success:
                raise OSError(outcome.message)

        self.screenshot_service = ScreenshotService(
            desktop_configuration,
            PillowScreenshotBackend(),
            screenshot_root,
            opener=WindowsPathOpener(),
            deleter=recycle_screenshot,
        )
        self.desktop_information_service = DesktopInformationService(
            desktop_configuration,
            TkScreenInformationProvider(),
            WindowsWindowInformationProvider(),
        )
        workflow_configuration = self.settings.workflow_configuration
        workflow_validator = WorkflowValidator(workflow_configuration)

        def inert_workflow_step(
            step: WorkflowStep, context: Mapping[str, JsonValue]
        ) -> JsonValue:
            del context
            return step.arguments.get("result")

        workflow_executor = WorkflowExecutor(
            workflow_configuration,
            workflow_validator,
            {
                WorkflowStepType.ASSIGN: inert_workflow_step,
                WorkflowStepType.CONDITION: inert_workflow_step,
                WorkflowStepType.DISPLAY_MESSAGE: inert_workflow_step,
                WorkflowStepType.STOP: inert_workflow_step,
            },
        )
        self.workflow_service = WorkflowService(
            workflow_configuration,
            WorkflowRepository(database_factory),
            WorkflowRunRepository(database_factory),
            workflow_validator,
            WorkflowPlanner(workflow_validator),
            workflow_executor,
        )
        plugin_configuration = self.settings.plugin_configuration
        plugin_root = (
            database_path.parent / "plugins"
            if database_path is not None
            else data_dir() / "plugins"
        )
        plugin_validator = PluginValidator(plugin_configuration)
        plugin_repository = PluginRepository(database_factory)
        plugin_permissions = PluginPermissionService(plugin_repository)
        self.plugin_manager = PluginManager(
            plugin_configuration,
            PluginDiscovery(
                plugin_configuration,
                plugin_validator,
                (plugin_root,),
            ),
            PluginPackageInstaller(
                plugin_configuration,
                plugin_validator,
                plugin_root,
                maximum_compression_ratio=(
                    self.settings.security_configuration.maximum_archive_compression_ratio
                ),
            ),
            plugin_validator,
            plugin_repository,
            plugin_permissions,
            PluginLifecycle(
                plugin_configuration,
                PluginLoader(plugin_configuration, plugin_validator),
            ),
            PluginRegistry(),
        )
        self.plugin_preference_access = PluginPreferenceAccess(
            self.preference_resolver,
            lambda plugin_id, version, fingerprint, permission: (
                plugin_permissions.require(
                    plugin_id,
                    version,
                    fingerprint,
                    PluginPermission(permission),
                )
            ),
        )
        ai_configuration = self.settings.ai_configuration
        ai_providers = AiProviderRegistry()
        if (
            ai_configuration.provider == "loopback-http"
            and ai_configuration.endpoint is not None
        ):
            ai_providers.register(
                LoopbackHttpAiProvider(
                    ai_configuration.endpoint,
                    timeout_seconds=ai_configuration.generation_timeout_seconds,
                    maximum_response_bytes=(
                        ai_configuration.maximum_response_characters * 4
                    ),
                )
            )
        ai_models = AiModelRegistry(ai_configuration, ai_providers)
        if (
            ai_configuration.provider == "loopback-http"
            and ai_configuration.default_generation_model is not None
        ):
            ai_models.register(
                AiModelDescriptor(
                    ai_configuration.default_generation_model,
                    ai_configuration.default_generation_model,
                    "loopback-http",
                    frozenset({AiModelCapability.GENERATION}),
                    provider_model_name=ai_configuration.default_generation_model,
                    maximum_output_length=(
                        ai_configuration.maximum_response_characters
                    ),
                )
            )
        self.ai_service = AiService(
            ai_configuration,
            ai_models,
            AiResourceManager(ai_configuration, ai_providers, ai_models),
        )
        self.ai_knowledge_assistant = AiKnowledgeAssistant(
            self.ai_service, self.knowledge_service
        )
        self.ai_proposal_service = AiProposalService(self.ai_service)
        self.plugin_ai_access = PluginAiAccess(
            self.ai_service,
            lambda plugin_id, version, fingerprint, permission: (
                plugin_permissions.require(
                    plugin_id,
                    version,
                    fingerprint,
                    PluginPermission(permission),
                )
            ),
        )
        self.notifications = NotificationCenter(
            get_logger("scheduling"),
            speech_enabled=self.settings.scheduling_configuration.speak_notifications,
        )
        self.scheduler = SchedulerEngine(
            self.settings.scheduling_configuration,
            scheduling_repository,
            self.notifications,
        )

        personalized_user = dict(self.settings.user)
        preferred_name = self.preference_resolver.resolve("display_name").value
        if isinstance(preferred_name, str) and preferred_name.strip():
            personalized_user["display_name"] = preferred_name
        self.session = OmegaSession(
            personalized_user,
            self.settings.assistant,
            parser=CommandParser(
                command_aliases=create_default_aliases(
                    self.settings.localization_configuration
                ),
                language=self.localization_service.active_language,
                security_configuration=self.settings.security_configuration,
            ),
            security_configuration=self.settings.security_configuration,
            greeting_builder=self.personalization_context.greeting,
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
            scheduling_dispatcher=SchedulingActionDispatcher(
                scheduling_service, safety_gateway
            ),
            productivity_dispatcher=ProductivityActionDispatcher(
                self.productivity_service,
                safety_gateway,
                self.productivity_export_service,
                self.productivity_import_service,
            ),
            knowledge_dispatcher=KnowledgeActionDispatcher(
                self.knowledge_service,
                safety_gateway,
                self.knowledge_export_service,
            ),
            email_dispatcher=EmailActionDispatcher(
                self.email_service,
                safety_gateway,
            ),
            calendar_dispatcher=CalendarActionDispatcher(
                self.calendar_service,
                safety_gateway,
            ),
            desktop_utility_dispatcher=DesktopUtilityActionDispatcher(
                self.clipboard_service,
                self.screenshot_service,
                self.desktop_information_service,
                safety_gateway,
                save_text=self._save_clipboard_text,
                create_note=self._create_clipboard_note,
            ),
            workflow_dispatcher=WorkflowDispatcher(
                self.workflow_service,
                safety_gateway,
            ),
            plugin_dispatcher=PluginDispatcher(
                self.plugin_manager,
                safety_gateway,
            ),
            ai_dispatcher=AiDispatcher(self.ai_service, safety_gateway),
            preference_dispatcher=PreferenceDispatcher(
                self.preference_service,
                self.profile_export_service,
                self.profile_import_service,
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

    def _save_clipboard_text(self, name: str, text: str, command_id: UUID) -> str:
        from uuid import uuid4

        created = self.file_manager.create_file(name, None, uuid4(), command_id)
        if not created.success:
            return created.user_message
        written = self.file_manager.write_text_file(
            name, None, text, uuid4(), command_id
        )
        return written.user_message

    def _create_clipboard_note(self, title: str, text: str, command_id: UUID) -> str:
        note = self.productivity_service.create_note(title, text, command_id=command_id)
        return f"Created note {note.title}."

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
            self._start_background_services()
            self.logger.info("Omega project foundation initialized successfully.")
            return TerminalInterface(
                self.session,
                notifications=self.notifications,
                localization=self.localization_service,
                accessibility=self.accessibility_service,
                input_func=input_func,
                output_func=output_func,
            ).run()
        except OSError as error:
            raise InitializationError(
                "Omega could not complete startup logging."
            ) from error
        finally:
            self.shutdown()

    def run_gui(self) -> int:
        """Run the optional desktop presentation over this composition root."""

        from omega.gui.application import OmegaGuiApplication

        self.logger.info("Starting Omega's optional desktop interface.")
        self._start_background_services()
        try:
            return OmegaGuiApplication(self).run()
        finally:
            self.shutdown()

    def _start_background_services(self) -> None:
        """Start explicitly owned workers only when an application mode runs."""

        self.scheduler.start()

    def shutdown(self) -> None:
        """Release only resources explicitly owned by this Omega instance."""

        self.browser_manager.shutdown()
        self.scheduler.stop()
        self.plugin_manager.shutdown()
        self.ai_service.shutdown()

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
        service = VoiceService(
            configuration,
            self.session,
            self.safety_gateway,
            microphone,
            recognizer,
            speaker,
            event_sink=event_sink,
            logger=get_logger("voice"),
        )
        self.notifications.set_speaker(service.speaker)
        return service

    def run_voice(
        self,
        *,
        output_func: Callable[[str], None] = print,
    ) -> int:
        """Run explicit terminal voice mode with safe text-only fallback."""

        from omega.voice.terminal import VoiceTerminalInterface

        try:
            self._start_background_services()
            return VoiceTerminalInterface(
                lambda sink: self.create_voice_service(event_sink=sink),
                output_func=output_func,
            ).run()
        finally:
            self.browser_manager.shutdown()
            self.scheduler.stop()

    def list_audio_devices(self) -> tuple[AudioDevice, ...]:
        """Enumerate bounded safe microphone metadata on explicit request."""

        from omega.voice.microphone import SoundDeviceMicrophone

        configuration = self.voice_configuration
        return SoundDeviceMicrophone(
            device=configuration.microphone_device,
            sample_rate_hz=configuration.sample_rate_hz,
            block_size=configuration.audio_block_size,
        ).list_devices()
