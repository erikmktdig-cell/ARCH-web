"""W07 application errors."""

from arch_web.domain.errors import WebContractError


class BackendEngineeringError(WebContractError):
    """Base W07 failure."""


class BackendPreparationError(BackendEngineeringError):
    """Backend assignment evidence is stale or unauthorized."""


class BackendProposalError(BackendEngineeringError):
    """Backend proposal cannot become an executable W05 change set."""


class UnsupportedBackendStackError(BackendEngineeringError):
    """No explicit adapter supports the resolved backend stack."""


__all__ = (
    "BackendEngineeringError",
    "BackendPreparationError",
    "BackendProposalError",
    "UnsupportedBackendStackError",
)
