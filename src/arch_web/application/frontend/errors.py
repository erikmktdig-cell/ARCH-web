"""W06 application errors."""

from arch_web.domain.errors import WebContractError


class FrontendEngineeringError(WebContractError):
    """Base W06 failure."""


class FrontendPreparationError(FrontendEngineeringError):
    """Assignment evidence is stale or outside authority."""


class FrontendAuthorizationError(FrontendEngineeringError):
    """Runtime authorization preconditions failed."""


class FrontendProposalError(FrontendEngineeringError):
    """A proposal cannot become an executable W05 change set."""


class UnsupportedFrontendStackError(FrontendEngineeringError):
    """No explicit adapter supports the resolved W05 stack."""


__all__ = (
    "FrontendAuthorizationError",
    "FrontendEngineeringError",
    "FrontendPreparationError",
    "FrontendProposalError",
    "UnsupportedFrontendStackError",
)
