"""Immutable W09 commands and results."""

from __future__ import annotations

from dataclasses import dataclass

from arch_runtime import ApplyTransitionResult

from arch_web.domain._base import WebContractRecord, require_text
from arch_web.domain.enums import WebLifecycleStatus, WebRoute
from arch_web.domain.qa import ReleaseReadinessPackage
from arch_web.domain.references import EvidenceRef
from arch_web.domain.release import (
    DeploymentApprovalPackage,
    DeploymentExecutionAuthorization,
    DeploymentPlan,
    DeploymentProviderProfile,
    DeploymentReceipt,
    DeploymentStrategy,
    EnvironmentConfigContract,
    PostDeployVerificationEvidence,
    PostDeployVerificationPlan,
    ProductionMigrationPlan,
    ReleaseArtifact,
    ReleaseCandidateManifest,
    ReleaseReviewPackage,
    ReleaseVersion,
    RollbackPlan,
    TargetEnvironment,
)


@dataclass(frozen=True, slots=True)
class PrepareReleaseCommand(WebContractRecord):
    contract_type = "prepare_release_command"
    project_id: str
    project_status: WebLifecycleStatus
    route: WebRoute
    runtime_record_version: int
    runtime_record_fingerprint: str
    release_readiness: ReleaseReadinessPackage
    release_version: ReleaseVersion | None
    artifacts: tuple[ReleaseArtifact, ...]
    resolved_stack_fingerprint: str
    target: TargetEnvironment
    config: EnvironmentConfigContract
    provider: DeploymentProviderProfile
    strategy: DeploymentStrategy
    migration_plan: ProductionMigrationPlan | None
    rollback_plan: RollbackPlan
    required_provenance: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for field in ("project_id", "runtime_record_fingerprint", "resolved_stack_fingerprint"):
            require_text(getattr(self, field), field)
        if self.runtime_record_version < 1:
            raise ValueError("runtime_record_version must be positive")


@dataclass(frozen=True, slots=True)
class PrepareReleaseResult(WebContractRecord):
    contract_type = "prepare_release_result"
    candidate: ReleaseCandidateManifest
    plan: DeploymentPlan
    review: ReleaseReviewPackage


@dataclass(frozen=True, slots=True)
class AuthorizeDeploymentCommand(WebContractRecord):
    contract_type = "authorize_deployment_command"
    prepared: PrepareReleaseResult
    target: TargetEnvironment
    provider: DeploymentProviderProfile
    migration_plan: ProductionMigrationPlan | None
    execution_id: str
    expected_prior_deployment_ref: str | None
    reviewer_evidence: tuple[EvidenceRef, ...]

    def __post_init__(self) -> None:
        require_text(self.execution_id, "execution_id")


@dataclass(frozen=True, slots=True)
class AuthorizeDeploymentResult(WebContractRecord):
    contract_type = "authorize_deployment_result"
    authorization: DeploymentExecutionAuthorization


@dataclass(frozen=True, slots=True)
class ExecuteDeploymentCommand(WebContractRecord):
    contract_type = "execute_deployment_command"
    prepared: PrepareReleaseResult
    authorization: DeploymentExecutionAuthorization
    artifact: ReleaseArtifact
    target: TargetEnvironment
    config: EnvironmentConfigContract
    migration_plan: ProductionMigrationPlan | None


@dataclass(frozen=True, slots=True)
class ExecuteDeploymentResult(WebContractRecord):
    contract_type = "execute_deployment_result"
    receipt: DeploymentReceipt


@dataclass(frozen=True, slots=True)
class VerifyDeploymentCommand(WebContractRecord):
    contract_type = "verify_deployment_command"
    prepared: PrepareReleaseResult
    receipt: DeploymentReceipt
    target: TargetEnvironment


@dataclass(frozen=True, slots=True)
class VerifyDeploymentResult(WebContractRecord):
    contract_type = "verify_deployment_result"
    plan: PostDeployVerificationPlan
    evidence: PostDeployVerificationEvidence


@dataclass(frozen=True, slots=True)
class ApproveDeploymentCommand(WebContractRecord):
    contract_type = "approve_deployment_command"
    project_status: WebLifecycleStatus
    prepared: PrepareReleaseResult
    authorization: DeploymentExecutionAuthorization
    receipt: DeploymentReceipt
    verification: VerifyDeploymentResult
    target: TargetEnvironment
    approval_evidence: tuple[EvidenceRef, ...]
    idempotency_key: str
    request_id: str
    transition_key: str
    expected_runtime_state: str
    expected_record_version: int
    expected_record_fingerprint: str
    expected_content_fingerprint: str
    actor_id: str
    actor_display_name: str | None = None

    def __post_init__(self) -> None:
        for field in (
            "idempotency_key",
            "request_id",
            "transition_key",
            "expected_runtime_state",
            "expected_record_fingerprint",
            "expected_content_fingerprint",
            "actor_id",
        ):
            require_text(getattr(self, field), field)
        if self.expected_record_version < 1:
            raise ValueError("expected_record_version must be positive")


@dataclass(frozen=True, slots=True)
class ApproveDeploymentResult(WebContractRecord):
    contract_type = "approve_deployment_result"
    package: DeploymentApprovalPackage
    runtime_result: ApplyTransitionResult


__all__ = tuple(name for name in globals() if name.endswith(("Command", "Result")))
