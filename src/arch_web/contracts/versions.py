"""Exact web contract version policy."""

from arch_web.domain.errors import UnsupportedWebContractVersionError

CURRENT_WEB_CONTRACT_VERSION = "0.1.0"
SUPPORTED_WEB_CONTRACT_VERSIONS = frozenset({CURRENT_WEB_CONTRACT_VERSION})


def require_supported_version(version: str) -> None:
    if version not in SUPPORTED_WEB_CONTRACT_VERSIONS:
        raise UnsupportedWebContractVersionError(f"Unsupported web contract version: {version!r}")


__all__ = ("CURRENT_WEB_CONTRACT_VERSION", "SUPPORTED_WEB_CONTRACT_VERSIONS")
