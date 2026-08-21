"""Structured W05 application errors."""


class WorkspacePreparationError(ValueError):
    pass


class WorkspaceExecutionError(RuntimeError):
    pass


class WorkspaceIdempotencyConflictError(WorkspaceExecutionError):
    pass


class ImplementationReadinessApprovalError(ValueError):
    pass


__all__ = (
    "ImplementationReadinessApprovalError",
    "WorkspaceExecutionError",
    "WorkspaceIdempotencyConflictError",
    "WorkspacePreparationError",
)
