"""Local W05 adapters."""

from arch_web.adapters.local.filesystem import LocalFileSystem
from arch_web.adapters.local.git import LocalGit
from arch_web.adapters.local.lock import LocalWorkspaceLocks
from arch_web.adapters.local.toolchain import LocalToolchainProbe, ToolProbeSpec

__all__ = (
    "LocalFileSystem",
    "LocalGit",
    "LocalToolchainProbe",
    "LocalWorkspaceLocks",
    "ToolProbeSpec",
)
