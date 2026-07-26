"""Bounded workflow-domain failures."""

from omega.core.exceptions import OmegaError


class WorkflowError(OmegaError):
    """Base safe workflow error."""


class WorkflowConfigurationError(WorkflowError):
    pass


class WorkflowValidationError(WorkflowError):
    pass


class WorkflowNotFoundError(WorkflowError):
    pass


class WorkflowStateError(WorkflowError):
    pass


class WorkflowPersistenceError(WorkflowError):
    pass


class WorkflowImportError(WorkflowError):
    pass
