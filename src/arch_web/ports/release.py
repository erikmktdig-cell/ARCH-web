"""Provider-neutral W09 execution boundary."""

from __future__ import annotations

from typing import Protocol

from arch_web.domain.release import (
    DeploymentExecutionAuthorization,
    DeploymentPlan,
    DeploymentReceipt,
    PostDeployVerificationEvidence,
    PostDeployVerificationPlan,
    ProductionMigrationPlan,
    ReleaseArtifact,
    RollbackExecutionEvidence,
    RollbackPlan,
    TargetEnvironment,
)


class DeploymentProviderPort(Protocol):
    @property
    def identity(self) -> str: ...

    def discover_capabilities(self) -> tuple[str, ...]: ...

    def deploy(
        self,
        authorization: DeploymentExecutionAuthorization,
        plan: DeploymentPlan,
        artifact: ReleaseArtifact,
        target: TargetEnvironment,
        migration_plan: ProductionMigrationPlan | None,
    ) -> DeploymentReceipt: ...

    def verify(
        self,
        plan: PostDeployVerificationPlan,
        receipt: DeploymentReceipt,
        target: TargetEnvironment,
    ) -> PostDeployVerificationEvidence: ...

    def rollback(
        self, plan: RollbackPlan, receipt: DeploymentReceipt
    ) -> RollbackExecutionEvidence: ...


__all__ = ("DeploymentProviderPort",)
