"""W08 application errors."""

from arch_web.domain.errors import WebContractError


class QAWorkflowError(WebContractError):
    """Base W08 failure."""


class QAPreparationError(QAWorkflowError):
    """Candidate or upstream evidence is stale or unauthorized."""


class QAExecutionError(QAWorkflowError):
    """Preview or QA execution cannot produce trustworthy evidence."""


class QAApprovalError(QAWorkflowError):
    """Testing or release-readiness approval is invalid."""


__all__ = ("QAApprovalError", "QAExecutionError", "QAPreparationError", "QAWorkflowError")
