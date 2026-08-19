"""Structured errors for pure web contracts."""

from __future__ import annotations


class WebContractError(ValueError):
    """Base error for web contract failures."""


class WebContractValidationError(WebContractError):
    """A contract violates a local or aggregate invariant."""


class UnsupportedWebContractVersionError(WebContractError):
    """A contract version has no exact decoder in this package."""


class WebContractIntegrityError(WebContractError):
    """Canonical bytes or their fingerprint do not match supplied evidence."""


class WebContractReferenceError(WebContractValidationError):
    """A typed contract reference is missing, stale, or points at the wrong target."""


__all__ = (
    "UnsupportedWebContractVersionError",
    "WebContractError",
    "WebContractIntegrityError",
    "WebContractReferenceError",
    "WebContractValidationError",
)
