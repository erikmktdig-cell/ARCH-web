"""Portable managed-path validation shared by W05 adapters."""

from __future__ import annotations

import re
from pathlib import Path, PurePosixPath, PureWindowsPath

from arch_web.domain.errors import WebContractValidationError

_DRIVE = re.compile(r"^[A-Za-z]:")
_FORBIDDEN_ROOTS = {".git", ".arch-web"}


def normalize_managed_path(value: str) -> str:
    """Return a canonical relative POSIX path or reject ambiguous/unsafe input."""
    if not value or value.strip() != value or "\x00" in value:
        raise WebContractValidationError("Managed path must be non-empty and normalized")
    if value.startswith(("/", "\\", "//")) or _DRIVE.match(value):
        raise WebContractValidationError("Managed path must be relative")
    windows = PureWindowsPath(value)
    if windows.is_absolute() or windows.drive or windows.root:
        raise WebContractValidationError("Managed path cannot use a drive or UNC root")
    normalized = value.replace("\\", "/")
    if "//" in normalized:
        raise WebContractValidationError("Managed path is ambiguous")
    parts = PurePosixPath(normalized).parts
    if not parts or any(part in {"", ".", ".."} for part in parts):
        raise WebContractValidationError("Managed path cannot traverse or contain dot segments")
    if parts[0].casefold() in _FORBIDDEN_ROOTS:
        raise WebContractValidationError("Managed path targets reserved metadata")
    return "/".join(parts)


def confined_path(root: Path, relative: str) -> Path:
    normalized = normalize_managed_path(relative)
    root_resolved = root.resolve(strict=False)
    candidate = root.joinpath(*normalized.split("/"))
    current = root_resolved
    for part in normalized.split("/"):
        current = current / part
        if current.exists() and current.is_symlink():
            target = current.resolve(strict=True)
            if target != root_resolved and root_resolved not in target.parents:
                raise WebContractValidationError("Managed path escapes through a link")
    resolved = candidate.resolve(strict=False)
    if resolved != root_resolved and root_resolved not in resolved.parents:
        raise WebContractValidationError("Managed path escapes workspace root")
    return candidate


__all__ = ("confined_path", "normalize_managed_path")
