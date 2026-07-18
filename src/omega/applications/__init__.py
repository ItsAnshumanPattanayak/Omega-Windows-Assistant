"""Public controlled Windows application-management services."""

from omega.applications.definitions import ApplicationDefinition
from omega.applications.discovery import WindowsApplicationDiscovery
from omega.applications.launcher import WindowsApplicationLauncher
from omega.applications.manager import (
    ApplicationManager,
    ApplicationOperationSettings,
)
from omega.applications.processes import (
    CRITICAL_PROCESS_NAMES,
    ApplicationProcessService,
)
from omega.applications.registry import ApplicationRegistry
from omega.applications.results import (
    ApplicationDiscoveryResult,
    ApplicationLaunchResult,
    ApplicationLaunchTarget,
    ApplicationProcess,
    LaunchTargetKind,
    ProcessInspectionResult,
    ProcessOperationResult,
)

__all__ = [
    "ApplicationDefinition",
    "ApplicationDiscoveryResult",
    "ApplicationLaunchResult",
    "ApplicationLaunchTarget",
    "ApplicationManager",
    "ApplicationOperationSettings",
    "ApplicationProcess",
    "ApplicationProcessService",
    "ApplicationRegistry",
    "CRITICAL_PROCESS_NAMES",
    "LaunchTargetKind",
    "ProcessInspectionResult",
    "ProcessOperationResult",
    "WindowsApplicationDiscovery",
    "WindowsApplicationLauncher",
]
