"""W02 workflow errors that do not shadow runtime failures."""


class RequirementsWorkflowError(ValueError):
    """Base error for invalid requirements workflow operations."""


class RequirementsIncompleteError(RequirementsWorkflowError):
    """Approval was attempted with blocking completeness gaps."""


class RequirementsConflictError(RequirementsWorkflowError):
    """Approval was attempted with unresolved contradictions."""


class RequirementsApprovalError(RequirementsWorkflowError):
    """Approval evidence or optimistic binding is invalid."""


__all__ = (
    "RequirementsApprovalError",
    "RequirementsConflictError",
    "RequirementsIncompleteError",
    "RequirementsWorkflowError",
)
