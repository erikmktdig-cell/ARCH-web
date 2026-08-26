"""Immutable W09 deployment and release contracts."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum, unique

from arch_web.contracts.versions import require_supported_version
from arch_web.domain._base import WebContractRecord, freeze_string_map, freeze_strings, require_text
from arch_web.domain.enums import WebLifecycleStatus, WebRoute
from arch_web.domain.qa import ReleaseReadinessPackage
from arch_web.domain.references import EvidenceRef
from arch_web.domain.workspace import ReconciliationStatus


def _records[T](values: tuple[T, ...], key: Callable[[T], str], label: str) -> tuple[T, ...]:
    ordered = tuple(sorted(values, key=key))
    keys = tuple(key(item) for item in ordered)
    if len(keys) != len(set(keys)):
        raise ValueError(f"{label} must be unique")
    return ordered


def _digest(value: str, field: str) -> None:
    require_text(value, field)
    raw = value.removeprefix("sha256:")
    if len(raw) != 64 or any(char not in "0123456789abcdef" for char in raw):
        raise ValueError(f"{field} must be a SHA-256 digest")


@unique
class EnvironmentClass(StrEnum):
    PREVIEW = "preview"
    STAGING = "staging"
    PRODUCTION = "production"


@unique
class DeploymentStrategy(StrEnum):
    DIRECT_REPLACE = "direct_replace"
    ROLLING = "rolling"
    BLUE_GREEN = "blue_green"
    CANARY = "canary"
    STATIC_PUBLICATION = "static_publication"


@unique
class DeploymentOutcome(StrEnum):
    NOT_EXECUTED = "not_executed"
    APPLIED_PENDING_VERIFICATION = "applied_pending_verification"
    DEPLOYED_VERIFIED = "deployed_verified"
    FAILED_NO_EXTERNAL_CHANGE = "failed_no_external_change"
    FAILED_ROLLED_BACK_VERIFIED = "failed_rolled_back_verified"
    RECONCILIATION_REQUIRED = "reconciliation_required"
    NOOP_ALREADY_DEPLOYED = "noop_already_deployed"


@unique
class MigrationRisk(StrEnum):
    NONE = "none"
    COMPATIBLE = "compatible"
    DESTRUCTIVE = "destructive"
    IRREVERSIBLE = "irreversible"


@unique
class RecoveryDisposition(StrEnum):
    ROLLBACK = "rollback"
    ROLL_FORWARD_ONLY = "roll_forward_only"
    NOT_APPLICABLE = "not_applicable"


@unique
class ReleaseFindingSeverity(StrEnum):
    BLOCKER = "blocker"
    CRITICAL = "critical"
    MAJOR = "major"
    ADVISORY = "advisory"


@unique
class ReleaseReadiness(StrEnum):
    BLOCKED = "blocked"
    READY_FOR_EXECUTION = "ready_for_execution"
    READY_FOR_APPROVAL = "ready_for_approval"
    APPROVED = "approved"


@dataclass(frozen=True, slots=True)
class ReleaseVersion(WebContractRecord):
    contract_type = "release_version"
    version: str
    source_commit: str
    source_tree_fingerprint: str

    def __post_init__(self) -> None:
        require_text(self.version, "version")
        require_text(self.source_commit, "source_commit")
        require_text(self.source_tree_fingerprint, "source_tree_fingerprint")
        if self.source_commit in {"HEAD", "main", "latest"}:
            raise ValueError("Release source must be pinned")


@dataclass(frozen=True, slots=True)
class ReleaseArtifact(WebContractRecord):
    contract_type = "release_artifact"
    artifact_id: str
    kind: str
    digest: str
    uri: str
    tested: bool
    lockfile_fingerprint: str | None = None
    builder_identity: str | None = None
    sbom_ref: str | None = None
    signature_ref: str | None = None

    def __post_init__(self) -> None:
        for field in ("artifact_id", "kind", "uri"):
            require_text(getattr(self, field), field)
        _digest(self.digest, "digest")
        for field in ("lockfile_fingerprint", "builder_identity", "sbom_ref", "signature_ref"):
            value = getattr(self, field)
            if value is not None:
                require_text(value, field)


@dataclass(frozen=True, slots=True)
class SecretReference(WebContractRecord):
    contract_type = "secret_reference"
    name: str
    provider_key: str
    required: bool = True

    def __post_init__(self) -> None:
        require_text(self.name, "name")
        require_text(self.provider_key, "provider_key")
        lowered = self.provider_key.casefold()
        if any(marker in lowered for marker in ("password=", "token=", "secret=", "-----begin")):
            raise ValueError("SecretReference must contain a reference, never a secret value")


@dataclass(frozen=True, slots=True)
class DeploymentProviderProfile(WebContractRecord):
    contract_type = "deployment_provider_profile"
    profile_id: str
    adapter_identity: str
    capabilities: tuple[str, ...]
    supported_strategies: tuple[DeploymentStrategy, ...]
    production_approved: bool

    def __post_init__(self) -> None:
        require_text(self.profile_id, "profile_id")
        require_text(self.adapter_identity, "adapter_identity")
        object.__setattr__(
            self, "capabilities", freeze_strings(self.capabilities, "capabilities", sort=True)
        )
        object.__setattr__(
            self,
            "supported_strategies",
            tuple(sorted(set(self.supported_strategies), key=lambda item: item.value)),
        )
        if not self.capabilities or not self.supported_strategies:
            raise ValueError("Deployment provider requires explicit capabilities and strategies")


@dataclass(frozen=True, slots=True)
class TargetEnvironment(WebContractRecord):
    contract_type = "target_environment"
    environment_id: str
    environment_class: EnvironmentClass
    provider_profile_id: str
    region: str
    base_url_intent: str
    datastore_target: str | None
    required_config_keys: tuple[str, ...]
    allowed_config_keys: tuple[str, ...]
    required_secret_refs: tuple[str, ...]
    health_path: str
    tls_required: bool
    canonical_host: str | None = None

    def __post_init__(self) -> None:
        for field in (
            "environment_id",
            "provider_profile_id",
            "region",
            "base_url_intent",
            "health_path",
        ):
            require_text(getattr(self, field), field)
        for field in ("datastore_target", "canonical_host"):
            value = getattr(self, field)
            if value is not None:
                require_text(value, field)
        for field in ("required_config_keys", "allowed_config_keys", "required_secret_refs"):
            object.__setattr__(self, field, freeze_strings(getattr(self, field), field, sort=True))
        if not self.health_path.startswith("/"):
            raise ValueError("health_path must be absolute")


@dataclass(frozen=True, slots=True)
class EnvironmentConfigContract(WebContractRecord):
    contract_type = "environment_config_contract"
    config_id: str
    environment_id: str
    values: tuple[tuple[str, str], ...]
    secret_refs: tuple[SecretReference, ...]
    derived_values: tuple[tuple[str, str], ...] = ()

    def __post_init__(self) -> None:
        require_text(self.config_id, "config_id")
        require_text(self.environment_id, "environment_id")
        object.__setattr__(self, "values", freeze_string_map(self.values, "values"))
        object.__setattr__(
            self, "derived_values", freeze_string_map(self.derived_values, "derived_values")
        )
        object.__setattr__(
            self, "secret_refs", _records(self.secret_refs, lambda item: item.name, "secret refs")
        )


@dataclass(frozen=True, slots=True)
class ProductionMigrationPlan(WebContractRecord):
    contract_type = "production_migration_plan"
    plan_id: str
    target_datastore: str
    expected_schema_version: str
    migration_ids: tuple[str, ...]
    migration_checksums: tuple[str, ...]
    risk: MigrationRisk
    backup_required: bool
    authorized_irreversible: bool
    rollback_compatible: bool
    postcondition_schema_version: str

    def __post_init__(self) -> None:
        for field in (
            "plan_id",
            "target_datastore",
            "expected_schema_version",
            "postcondition_schema_version",
        ):
            require_text(getattr(self, field), field)
        object.__setattr__(
            self, "migration_ids", freeze_strings(self.migration_ids, "migration_ids")
        )
        object.__setattr__(
            self,
            "migration_checksums",
            freeze_strings(self.migration_checksums, "migration_checksums"),
        )
        if len(self.migration_ids) != len(self.migration_checksums):
            raise ValueError("Migration IDs and checksums must align")
        for checksum in self.migration_checksums:
            _digest(checksum, "migration checksum")


@dataclass(frozen=True, slots=True)
class ProductionMigrationExecutionEvidence(WebContractRecord):
    contract_type = "production_migration_execution_evidence"
    plan_fingerprint: str
    target_datastore: str
    before_version: str
    after_version: str
    applied_migration_ids: tuple[str, ...]
    success: bool
    evidence_digest: str

    def __post_init__(self) -> None:
        for field in ("plan_fingerprint", "target_datastore", "before_version", "after_version"):
            require_text(getattr(self, field), field)
        object.__setattr__(
            self,
            "applied_migration_ids",
            freeze_strings(self.applied_migration_ids, "applied_migration_ids"),
        )
        _digest(self.evidence_digest, "evidence_digest")


@dataclass(frozen=True, slots=True)
class RollbackPlan(WebContractRecord):
    contract_type = "rollback_plan"
    plan_id: str
    disposition: RecoveryDisposition
    prior_artifact_digest: str | None
    prior_deployment_ref: str | None
    migration_compatible: bool
    verification_checks: tuple[str, ...]

    def __post_init__(self) -> None:
        require_text(self.plan_id, "plan_id")
        if self.prior_artifact_digest is not None:
            _digest(self.prior_artifact_digest, "prior_artifact_digest")
        if self.prior_deployment_ref is not None:
            require_text(self.prior_deployment_ref, "prior_deployment_ref")
        object.__setattr__(
            self,
            "verification_checks",
            freeze_strings(self.verification_checks, "verification_checks", sort=True),
        )
        if self.disposition is RecoveryDisposition.ROLLBACK and not self.migration_compatible:
            raise ValueError("Rollback cannot be claimed across incompatible migrations")


@dataclass(frozen=True, slots=True)
class RollbackExecutionEvidence(WebContractRecord):
    contract_type = "rollback_execution_evidence"
    plan_fingerprint: str
    provider_deployment_id: str
    success: bool
    verified: bool
    evidence_digest: str

    def __post_init__(self) -> None:
        require_text(self.plan_fingerprint, "plan_fingerprint")
        require_text(self.provider_deployment_id, "provider_deployment_id")
        _digest(self.evidence_digest, "evidence_digest")
        if self.verified and not self.success:
            raise ValueError("Failed rollback cannot be verified successful")


@dataclass(frozen=True, slots=True)
class ReleaseCandidateManifest(WebContractRecord):
    contract_type = "release_candidate_manifest"
    contract_version: str
    candidate_id: str
    project_id: str
    route: WebRoute
    runtime_state: WebLifecycleStatus
    runtime_record_version: int
    runtime_record_fingerprint: str
    release_readiness: ReleaseReadinessPackage
    release_version: ReleaseVersion | None
    artifacts: tuple[ReleaseArtifact, ...]
    resolved_stack_fingerprint: str
    migration_plan_ref: str | None
    environment_config_ref: str

    def __post_init__(self) -> None:
        require_supported_version(self.contract_version)
        for field in (
            "candidate_id",
            "project_id",
            "runtime_record_fingerprint",
            "resolved_stack_fingerprint",
            "environment_config_ref",
        ):
            require_text(getattr(self, field), field)
        if self.runtime_state is not WebLifecycleStatus.RELEASE_READY:
            raise ValueError("Release candidate requires RELEASE_READY")
        if self.runtime_record_version < 1:
            raise ValueError("runtime_record_version must be positive")
        object.__setattr__(
            self, "artifacts", _records(self.artifacts, lambda item: item.artifact_id, "artifacts")
        )
        if not self.artifacts or not all(item.tested for item in self.artifacts):
            raise ValueError("Release candidate requires tested artifacts")
        if self.release_readiness.project_id != self.project_id:
            raise ValueError("Release-readiness project mismatch")
        if self.release_version is not None:
            if (
                self.release_version.source_tree_fingerprint
                != self.release_readiness.source_tree_fingerprint
            ):
                raise ValueError("Release source tree is stale")
            if self.release_version.source_commit != self.release_readiness.git_head:
                raise ValueError("Release Git commit is stale")


@dataclass(frozen=True, slots=True)
class DeploymentStep(WebContractRecord):
    contract_type = "deployment_step"
    step_id: str
    order: int
    action: str
    mutating: bool

    def __post_init__(self) -> None:
        require_text(self.step_id, "step_id")
        require_text(self.action, "action")
        if self.order < 1:
            raise ValueError("Deployment step order must be positive")


@dataclass(frozen=True, slots=True)
class DeploymentPlan(WebContractRecord):
    contract_type = "deployment_plan"
    contract_version: str
    plan_id: str
    candidate_fingerprint: str
    environment_fingerprint: str
    config_fingerprint: str
    provider_profile_fingerprint: str
    provider_adapter_identity: str
    artifact_digest: str
    strategy: DeploymentStrategy
    migration_plan_fingerprint: str | None
    rollback_plan: RollbackPlan
    steps: tuple[DeploymentStep, ...]

    def __post_init__(self) -> None:
        require_supported_version(self.contract_version)
        for field in (
            "plan_id",
            "candidate_fingerprint",
            "environment_fingerprint",
            "config_fingerprint",
            "provider_profile_fingerprint",
            "provider_adapter_identity",
        ):
            require_text(getattr(self, field), field)
        _digest(self.artifact_digest, "artifact_digest")
        ordered = tuple(sorted(self.steps, key=lambda item: item.order))
        if tuple(item.order for item in ordered) != tuple(range(1, len(ordered) + 1)):
            raise ValueError("Deployment steps must be contiguous")
        object.__setattr__(self, "steps", ordered)


@dataclass(frozen=True, slots=True)
class DeploymentExecutionAuthorization(WebContractRecord):
    contract_type = "deployment_execution_authorization"
    authorization_id: str
    execution_id: str
    candidate_fingerprint: str
    plan_fingerprint: str
    environment_id: str
    provider_profile_id: str
    artifact_digest: str
    migration_plan_fingerprint: str | None
    expected_prior_deployment_ref: str | None
    reviewer_evidence: tuple[EvidenceRef, ...]
    authorized: bool

    def __post_init__(self) -> None:
        for field in (
            "authorization_id",
            "execution_id",
            "candidate_fingerprint",
            "plan_fingerprint",
            "environment_id",
            "provider_profile_id",
        ):
            require_text(getattr(self, field), field)
        _digest(self.artifact_digest, "artifact_digest")
        object.__setattr__(
            self,
            "reviewer_evidence",
            _records(self.reviewer_evidence, lambda item: item.evidence_id, "reviewer evidence"),
        )


@dataclass(frozen=True, slots=True)
class DeploymentAttempt(WebContractRecord):
    contract_type = "deployment_attempt"
    execution_id: str
    candidate_fingerprint: str
    plan_fingerprint: str
    provider_profile_id: str
    prior_deployment_ref: str | None

    def __post_init__(self) -> None:
        for field in (
            "execution_id",
            "candidate_fingerprint",
            "plan_fingerprint",
            "provider_profile_id",
        ):
            require_text(getattr(self, field), field)
        _digest(self.candidate_fingerprint, "candidate_fingerprint")
        _digest(self.plan_fingerprint, "plan_fingerprint")


@dataclass(frozen=True, slots=True)
class DeploymentReceipt(WebContractRecord):
    contract_type = "deployment_receipt"
    execution_id: str
    candidate_fingerprint: str
    plan_fingerprint: str
    provider_profile_id: str
    environment_id: str
    artifact_digest: str
    provider_deployment_id: str
    previous_deployment_ref: str | None
    endpoint: str | None
    observed_artifact_digest: str | None
    outcome: DeploymentOutcome
    reconciliation_status: ReconciliationStatus
    adapter_identity: str
    sanitized_evidence_digests: tuple[str, ...]
    migration_evidence: ProductionMigrationExecutionEvidence | None = None

    def __post_init__(self) -> None:
        for field in (
            "execution_id",
            "candidate_fingerprint",
            "plan_fingerprint",
            "provider_profile_id",
            "environment_id",
            "provider_deployment_id",
            "adapter_identity",
        ):
            require_text(getattr(self, field), field)
        _digest(self.artifact_digest, "artifact_digest")
        if self.observed_artifact_digest is not None:
            _digest(self.observed_artifact_digest, "observed_artifact_digest")
        object.__setattr__(
            self,
            "sanitized_evidence_digests",
            freeze_strings(
                self.sanitized_evidence_digests, "sanitized_evidence_digests", sort=True
            ),
        )
        if (
            self.outcome is DeploymentOutcome.RECONCILIATION_REQUIRED
            and self.reconciliation_status is not ReconciliationStatus.REQUIRED
        ):
            raise ValueError("Uncertain deployment requires reconciliation")


@dataclass(frozen=True, slots=True)
class PostDeployVerificationPlan(WebContractRecord):
    contract_type = "post_deploy_verification_plan"
    plan_id: str
    candidate_fingerprint: str
    receipt_fingerprint: str
    expected_artifact_digest: str
    health_path: str
    checks: tuple[str, ...]

    def __post_init__(self) -> None:
        for field in ("plan_id", "candidate_fingerprint", "receipt_fingerprint", "health_path"):
            require_text(getattr(self, field), field)
        _digest(self.expected_artifact_digest, "expected_artifact_digest")
        object.__setattr__(self, "checks", freeze_strings(self.checks, "checks", sort=True))


@dataclass(frozen=True, slots=True)
class PostDeployVerificationEvidence(WebContractRecord):
    contract_type = "post_deploy_verification_evidence"
    verification_id: str
    plan_fingerprint: str
    receipt_fingerprint: str
    observed_artifact_digest: str
    check_results: tuple[tuple[str, str], ...]
    endpoint_reachable: bool
    health_passed: bool
    critical_smoke_passed: bool
    backend_passed: bool
    security_passed: bool
    tls_passed: bool
    mock_leakage_detected: bool
    passed: bool

    def __post_init__(self) -> None:
        for field in ("verification_id", "plan_fingerprint", "receipt_fingerprint"):
            require_text(getattr(self, field), field)
        _digest(self.observed_artifact_digest, "observed_artifact_digest")
        object.__setattr__(
            self, "check_results", freeze_string_map(self.check_results, "check_results")
        )
        expected = all(
            (
                self.endpoint_reachable,
                self.health_passed,
                self.critical_smoke_passed,
                self.backend_passed,
                self.security_passed,
                self.tls_passed,
                not self.mock_leakage_detected,
            )
        )
        if self.passed != expected:
            raise ValueError("Verification summary contradicts checks")


@dataclass(frozen=True, slots=True)
class ReleaseFinding(WebContractRecord):
    contract_type = "release_finding"
    finding_id: str
    code: str
    severity: ReleaseFindingSeverity
    blocking: bool
    message: str
    evidence_refs: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for field in ("finding_id", "code", "message"):
            require_text(getattr(self, field), field)
        object.__setattr__(
            self, "evidence_refs", freeze_strings(self.evidence_refs, "evidence_refs", sort=True)
        )
        if self.severity is ReleaseFindingSeverity.BLOCKER and not self.blocking:
            raise ValueError("Blocker severity must block")


@dataclass(frozen=True, slots=True)
class ReleaseReviewPackage(WebContractRecord):
    contract_type = "release_review_package"
    review_id: str
    candidate_fingerprint: str
    plan_fingerprint: str
    findings: tuple[ReleaseFinding, ...]
    readiness: ReleaseReadiness

    def __post_init__(self) -> None:
        for field in ("review_id", "candidate_fingerprint", "plan_fingerprint"):
            require_text(getattr(self, field), field)
        object.__setattr__(
            self,
            "findings",
            _records(self.findings, lambda item: item.finding_id, "release findings"),
        )
        blocked = any(item.blocking for item in self.findings)
        if blocked != (self.readiness is ReleaseReadiness.BLOCKED):
            raise ValueError("Release readiness contradicts findings")


@dataclass(frozen=True, slots=True)
class DeploymentApprovalPackage(WebContractRecord):
    contract_type = "deployment_approval_package"
    contract_version: str
    package_id: str
    project_id: str
    route: WebRoute
    runtime_state: WebLifecycleStatus
    runtime_record_version: int
    runtime_record_fingerprint: str
    release_readiness_fingerprint: str
    candidate_fingerprint: str
    environment_fingerprint: str
    plan_fingerprint: str
    authorization_fingerprint: str
    receipt_fingerprint: str
    verification_fingerprint: str
    rollback_plan_fingerprint: str
    findings: tuple[ReleaseFinding, ...]
    reconciliation_status: ReconciliationStatus
    reviewer_evidence: tuple[EvidenceRef, ...]
    approved: bool

    def __post_init__(self) -> None:
        require_supported_version(self.contract_version)
        for field in (
            "package_id",
            "project_id",
            "runtime_record_fingerprint",
            "release_readiness_fingerprint",
            "candidate_fingerprint",
            "environment_fingerprint",
            "plan_fingerprint",
            "authorization_fingerprint",
            "receipt_fingerprint",
            "verification_fingerprint",
            "rollback_plan_fingerprint",
        ):
            require_text(getattr(self, field), field)
        object.__setattr__(
            self,
            "findings",
            _records(self.findings, lambda item: item.finding_id, "release findings"),
        )
        object.__setattr__(
            self,
            "reviewer_evidence",
            _records(self.reviewer_evidence, lambda item: item.evidence_id, "reviewer evidence"),
        )
        valid = (
            self.runtime_state is WebLifecycleStatus.RELEASE_READY
            and self.reconciliation_status is ReconciliationStatus.CLEAN
            and not any(item.blocking for item in self.findings)
            and bool(self.reviewer_evidence)
        )
        if self.approved != valid:
            raise ValueError("Deployment approval contradicts bound evidence")


__all__ = tuple(
    name
    for name in globals()
    if not name.startswith("_") and name not in {"Callable", "StrEnum", "WebContractRecord"}
)
