"""Approved bridges to public ARCH Runtime APIs."""

from arch_web.runtime_bridge.architecture import approve_architecture
from arch_web.runtime_bridge.frontend import authorize_frontend
from arch_web.runtime_bridge.qa import approve_release_readiness, authorize_testing
from arch_web.runtime_bridge.release import approve_deployment
from arch_web.runtime_bridge.requirements import approve_requirements
from arch_web.runtime_bridge.ui import approve_ui_specification
from arch_web.runtime_bridge.workflow import (
    WEB_TRANSITION_DEFINITIONS,
    WEB_TRANSITION_REGISTRY,
    WEB_WORKFLOW_DEFINITION,
    WEB_WORKFLOW_DEFINITION_REGISTRY,
    WEB_WORKFLOW_ID,
    WEB_WORKFLOW_NAMESPACE,
    InitializeWebLifecycleCommand,
    WebLifecycleEvidence,
    WebWorkflowAuthorityError,
    initialize_web_lifecycle,
    read_web_lifecycle,
)
from arch_web.runtime_bridge.workspace import approve_implementation_readiness

__all__ = (
    "WEB_TRANSITION_DEFINITIONS",
    "WEB_TRANSITION_REGISTRY",
    "WEB_WORKFLOW_DEFINITION",
    "WEB_WORKFLOW_DEFINITION_REGISTRY",
    "WEB_WORKFLOW_ID",
    "WEB_WORKFLOW_NAMESPACE",
    "InitializeWebLifecycleCommand",
    "WebLifecycleEvidence",
    "WebWorkflowAuthorityError",
    "approve_architecture",
    "approve_deployment",
    "approve_implementation_readiness",
    "approve_release_readiness",
    "approve_requirements",
    "approve_ui_specification",
    "authorize_frontend",
    "authorize_testing",
    "initialize_web_lifecycle",
    "read_web_lifecycle",
)
