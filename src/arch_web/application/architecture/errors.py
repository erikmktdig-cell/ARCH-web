"""Structured W03 workflow errors."""

from arch_web.domain.errors import WebContractError


class ArchitectureWorkflowError(WebContractError):
    """Base error for information-architecture workflow failures."""


class ArchitecturePreparationError(ArchitectureWorkflowError):
    """Approved requirements evidence is absent, stale, or inconsistent."""


class ArchitectureApprovalError(ArchitectureWorkflowError):
    """Architecture evidence is not eligible for explicit approval."""


__all__ = (
    "ArchitectureApprovalError",
    "ArchitecturePreparationError",
    "ArchitectureWorkflowError",
)
