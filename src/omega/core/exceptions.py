"""Project-specific exception hierarchy."""


class OmegaError(Exception):
    """Base class for all Omega-specific errors."""


class ConfigurationError(OmegaError):
    """Raised when Omega configuration is missing or invalid."""


class InitializationError(OmegaError):
    """Raised when the application cannot initialize safely."""


class UnsupportedPlatformError(OmegaError):
    """Raised when the current runtime does not meet Omega requirements."""


class ModelValidationError(OmegaError):
    """Raised when a typed Omega model contains an invalid state or value."""


class SessionError(OmegaError):
    """Base exception for invalid Omega text-session behavior."""


class InvalidSessionTransitionError(SessionError):
    """Raised when a session state transition is not permitted."""


class ApplicationError(OmegaError):
    """Base exception for invalid controlled-application behavior."""


class ApplicationRegistryError(ApplicationError):
    """Raised when the allowlisted application registry is invalid."""


class FileManagementError(OmegaError):
    """Base exception for controlled file-management failures."""


class FileLocationError(FileManagementError):
    """Raised when an approved logical file location cannot be resolved."""


class FilePathValidationError(FileManagementError):
    """Raised when a requested file path fails safety validation."""


class FileConflictError(FileManagementError):
    """Raised when a safe file operation would replace an existing file."""


class FileReadError(FileManagementError):
    """Raised when a controlled text read cannot be completed safely."""


class FileWriteError(FileManagementError):
    """Raised when a controlled text write cannot be completed safely."""


class FileOperationError(FileManagementError):
    """Raised when a controlled rename, copy, or move fails."""


class FileSearchError(FileManagementError):
    """Raised when a bounded file search cannot be completed safely."""


class FileOpenError(FileManagementError):
    """Raised when a validated document cannot be opened safely."""


class FolderManagementError(OmegaError):
    """Base exception for controlled folder-management failures."""


class FolderValidationError(FolderManagementError):
    """Raised when a folder name or path fails safety validation."""


class FolderCreationError(FolderManagementError):
    """Raised when one validated folder cannot be created safely."""


class FolderInspectionError(FolderManagementError):
    """Raised when bounded folder inspection cannot be completed safely."""


class FolderOperationError(FolderManagementError):
    """Raised when a folder rename, copy, or move cannot complete safely."""


class FolderConflictError(FolderOperationError):
    """Raised when an operation would merge with or replace a destination."""


class FolderResourceLimitError(FolderOperationError):
    """Raised when a folder tree exceeds a configured safety limit."""


class FolderCrossVolumeMoveError(FolderOperationError):
    """Raised when an unsafe destructive cross-volume move is requested."""


class FolderSearchError(FolderManagementError):
    """Raised when a bounded folder search cannot be completed safely."""


class FolderOpenError(FolderManagementError):
    """Raised when a validated directory cannot be opened safely."""
