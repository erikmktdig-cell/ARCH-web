"""Structured W09 workflow failures."""


class ReleaseWorkflowError(RuntimeError):
    """Base W09 workflow error."""


class ReleasePreparationError(ReleaseWorkflowError):
    """Release candidate or plan is not safe to prepare."""


class DeploymentAuthorizationError(ReleaseWorkflowError):
    """Deployment execution lacks exact authority."""


class DeploymentExecutionError(ReleaseWorkflowError):
    """Bounded provider execution failed."""


class DeploymentVerificationError(ReleaseWorkflowError):
    """Post-deployment evidence is invalid or failed."""


class DeploymentApprovalError(ReleaseWorkflowError):
    """Final Runtime deployment approval is invalid."""


__all__ = tuple(name for name in globals() if name.endswith("Error"))
