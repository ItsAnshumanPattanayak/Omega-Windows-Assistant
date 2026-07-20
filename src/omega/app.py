"""Application bootstrap for Omega's controlled text-session services."""

from __future__ import annotations

import sys
from collections.abc import Callable
from pathlib import Path

from omega.applications import (
    ApplicationManager,
    ApplicationOperationSettings,
    ApplicationProcessService,
    ApplicationRegistry,
    WindowsApplicationDiscovery,
    WindowsApplicationLauncher,
)
from omega.config.settings import Settings, load_settings
from omega.core.exceptions import InitializationError, UnsupportedPlatformError
from omega.execution import (
    ApplicationActionDispatcher,
    FileActionDispatcher,
    FolderActionDispatcher,
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
from omega.utils.constants import MINIMUM_PYTHON_VERSION
from omega.utils.logger import configure_logging, get_logger
from omega.utils.paths import log_dir


class OmegaApplication:
    """Initialize configuration, logging, and controlled application services."""

    def __init__(self, config_path: Path | None = None) -> None:
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
        )

        recovery_configuration = RecoveryConfiguration.from_mapping(
            self.settings.recovery
        )
        recovery_registry = RecoveryRegistry(recovery_configuration)
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
            safety_gateway=safety_gateway,
        )

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
