"""Approved ARCH Web adapter ports."""

from arch_web.ports.frontend import FrontendExecutorPort, FrontendStackAdapter
from arch_web.ports.workspace import FileSystemPort, VersionControlPort, WorkspaceLockPort

__all__: tuple[str, ...] = (
    "FileSystemPort",
    "FrontendExecutorPort",
    "FrontendStackAdapter",
    "VersionControlPort",
    "WorkspaceLockPort",
)
