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
        registry = ApplicationRegistry.from_file()
        manager = ApplicationManager(
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
            SafeFilePathResolver(locations, FilePathValidator()),
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
                file_settings.search_max_depth, file_settings.search_max_results
            ),
            WindowsFileOpener(),
            settings=file_settings,
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
            FolderOperations(folder_inspector, folder_validator),
            FolderSearch(folder_validator),
            WindowsFolderOpener(),
            settings=folder_settings,
            logger=get_logger("folders.manager"),
        )
        self.session = OmegaSession(
            self.settings.user,
            self.settings.assistant,
            logger=get_logger("session"),
            application_dispatcher=ApplicationActionDispatcher(manager, registry),
            file_dispatcher=FileActionDispatcher(file_manager),
            folder_dispatcher=FolderActionDispatcher(folder_manager),
        )
        self.logger.info(
            "%s %s initialized in %s mode.",
            self.settings.application_name,
            self.settings.application_version,
            self.settings.application.get("environment", "development"),
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
                self.session, input_func=input_func, output_func=output_func
            ).run()
        except OSError as error:
            raise InitializationError(
                "Omega could not complete startup logging."
            ) from error
