"""Structured W04 workflow errors."""

from arch_web.domain.errors import WebContractError


class UIDesignWorkflowError(WebContractError):
    """Base error for governed UI design workflow failures."""


class UIDesignPreparationError(UIDesignWorkflowError):
    """Upstream evidence or explicit design input is stale or inconsistent."""


class UIDesignApprovalError(UIDesignWorkflowError):
    """UI evidence is not eligible for governed approval."""


__all__ = ("UIDesignApprovalError", "UIDesignPreparationError", "UIDesignWorkflowError")
