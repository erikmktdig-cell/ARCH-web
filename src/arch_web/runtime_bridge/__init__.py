"""Approved bridges to public ARCH Runtime APIs."""

from arch_web.runtime_bridge.architecture import approve_architecture
from arch_web.runtime_bridge.requirements import approve_requirements
from arch_web.runtime_bridge.ui import approve_ui_specification

__all__ = ("approve_architecture", "approve_requirements", "approve_ui_specification")
