"""Approved bridges to public ARCH Runtime APIs."""

from arch_web.runtime_bridge.architecture import approve_architecture
from arch_web.runtime_bridge.requirements import approve_requirements
from arch_web.runtime_bridge.ui import approve_ui_specification
from arch_web.runtime_bridge.workspace import approve_implementation_readiness

__all__ = (
    "approve_architecture",
    "approve_implementation_readiness",
    "approve_requirements",
    "approve_ui_specification",
)
