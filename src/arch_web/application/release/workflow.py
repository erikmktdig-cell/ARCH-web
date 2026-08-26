"""Deterministic W09 planning and bounded provider orchestration."""

from __future__ import annotations

from arch_web.application.architecture.planning import semantic_id
from arch_web.application.release.errors import (
    DeploymentAuthorizationError,
    DeploymentExecutionError,
    DeploymentVerificationError,
    ReleasePreparationError,
)
from arch_web.application.release.models import (
    AuthorizeDeploymentCommand,
    AuthorizeDeploymentResult,
    ExecuteDeploymentCommand,
    ExecuteDeploymentResult,
    PrepareReleaseCommand,
    PrepareReleaseResult,
    VerifyDeploymentCommand,
    VerifyDeploymentResult,
)
from arch_web.contracts.versions import CURRENT_WEB_CONTRACT_VERSION
from arch_web.domain.enums import WebLifecycleStatus, WebRoute
from arch_web.domain.release import (
    DeploymentExecutionAuthorization,
    DeploymentOutcome,
    DeploymentPlan,
    DeploymentStep,
    DeploymentStrategy,
    EnvironmentClass,
    MigrationRisk,
    PostDeployVerificationPlan,
    RecoveryDisposition,
    ReleaseCandidateManifest,
    ReleaseFinding,
    ReleaseFindingSeverity,
    ReleaseReadiness,
    ReleaseReviewPackage,
)
from arch_web.domain.workspace import ReconciliationStatus
from arch_web.ports.release import DeploymentProviderPort

_SECRET_MARKERS = (
    "password=",
    "token=",
    "secret=",
    "api_key=",
    "-----begin",
    "ghp_",
    "github_pat_",
)


def _finding(code: str, message: str, *, blocking: bool = True) -> ReleaseFinding:
    return ReleaseFinding(
        semantic_id("RLF", {"code": code, "message": message}),
        code,
        ReleaseFindingSeverity.BLOCKER if blocking else ReleaseFindingSeverity.ADVISORY,
        blocking,
        message,
    )


def _config_findings(command: PrepareReleaseCommand) -> tuple[ReleaseFinding, ...]:
    target, config = command.target, command.config
    findings: list[ReleaseFinding] = []
    values = dict(config.values)
    secret_names = {item.name for item in config.secret_refs}
    if config.environment_id != target.environment_id:
        findings.append(_finding("environment_mismatch", "Configuration target is not approved"))
    missing = set(target.required_config_keys) - values.keys()
    unknown = values.keys() - set(target.allowed_config_keys)
    if missing:
        findings.append(_finding("missing_config", "Required production configuration is missing"))
    if unknown:
        findings.append(_finding("unknown_config", "Unapproved configuration key is present"))
    if set(target.required_secret_refs) - secret_names:
        findings.append(_finding("missing_secret_ref", "Required secret reference is missing"))
    for key, value in config.values:
        lowered = value.casefold()
        if any(marker in lowered for marker in _SECRET_MARKERS):
            findings.append(_finding("raw_secret", f"Raw secret-like value found in {key}"))
        if target.environment_class is EnvironmentClass.PRODUCTION:
            if any(
                marker in lowered
                for marker in ("localhost", "127.0.0.1", "test.db", "mock", "example.invalid")
            ):
                findings.append(
                    _finding(
                        "test_endpoint_leakage", f"Production value {key} targets a test system"
                    )
                )
            if any(marker in lowered for marker in ("changeme", "placeholder", "todo")):
                findings.append(
                    _finding("placeholder_config", f"Production value {key} is a placeholder")
                )
    return tuple(findings)


def _migration_findings(command: PrepareReleaseCommand) -> tuple[ReleaseFinding, ...]:
    plan = command.migration_plan
    if plan is None:
        return ()
    findings: list[ReleaseFinding] = []
    if command.target.datastore_target != plan.target_datastore:
        findings.append(
            _finding("migration_target_mismatch", "Migration targets the wrong datastore")
        )
    if plan.risk is MigrationRisk.DESTRUCTIVE and not plan.backup_required:
        findings.append(
            _finding(
                "unsafe_destructive_migration", "Destructive migration lacks recovery evidence"
            )
        )
    if plan.risk is MigrationRisk.IRREVERSIBLE and not plan.authorized_irreversible:
        findings.append(
            _finding("irreversible_migration", "Irreversible migration lacks explicit authority")
        )
    if (
        plan.risk is MigrationRisk.IRREVERSIBLE
        and command.rollback_plan.disposition is RecoveryDisposition.ROLLBACK
    ):
        findings.append(
            _finding("invalid_rollback_claim", "Irreversible migration cannot claim rollback")
        )
    return tuple(findings)


def _provenance_findings(command: PrepareReleaseCommand) -> tuple[ReleaseFinding, ...]:
    findings: list[ReleaseFinding] = []
    for requirement in sorted(set(command.required_provenance)):
        if requirement == "sbom" and any(item.sbom_ref is None for item in command.artifacts):
            findings.append(
                _finding("required_provenance_missing", "Required SBOM evidence is missing")
            )
        elif requirement == "signature" and any(
            item.signature_ref is None for item in command.artifacts
        ):
            findings.append(
                _finding("required_provenance_missing", "Required signature evidence is missing")
            )
        elif requirement not in {"sbom", "signature"}:
            findings.append(
                _finding("unsupported_provenance", f"Unsupported provenance policy: {requirement}")
            )
    return tuple(findings)


def prepare_release(command: PrepareReleaseCommand) -> PrepareReleaseResult:
    """Freeze an exact W08 candidate and derive a mutation-free deployment plan."""
    if command.project_status is not WebLifecycleStatus.RELEASE_READY:
        raise ReleasePreparationError("Release preparation requires RELEASE_READY")
    readiness = command.release_readiness
    if readiness.project_id != command.project_id:
        raise ReleasePreparationError("W08 release-readiness project mismatch")
    if command.release_version is not None and (
        command.release_version.source_commit != readiness.git_head
        or command.release_version.source_tree_fingerprint != readiness.source_tree_fingerprint
    ):
        raise ReleasePreparationError("W08 source or Git evidence is stale")
    if command.target.provider_profile_id != command.provider.profile_id:
        raise ReleasePreparationError("Target provider profile mismatch")
    if (
        command.target.environment_class is EnvironmentClass.PRODUCTION
        and not command.provider.production_approved
    ):
        raise ReleasePreparationError("Provider profile is not approved for production")
    if command.strategy not in command.provider.supported_strategies:
        raise ReleasePreparationError("Deployment strategy is unsupported")
    if command.route is WebRoute.CRITICAL and command.strategy is DeploymentStrategy.DIRECT_REPLACE:
        raise ReleasePreparationError("Critical route requires an explicit guarded strategy")
    candidate = ReleaseCandidateManifest(
        CURRENT_WEB_CONTRACT_VERSION,
        semantic_id(
            "RCM",
            {"project": command.project_id, "readiness": readiness, "artifacts": command.artifacts},
        ),
        command.project_id,
        command.route,
        command.project_status,
        command.runtime_record_version,
        command.runtime_record_fingerprint,
        readiness,
        command.release_version,
        command.artifacts,
        command.resolved_stack_fingerprint,
        None if command.migration_plan is None else command.migration_plan.canonical_fingerprint(),
        command.config.canonical_fingerprint(),
    )
    findings = tuple(
        sorted(
            {
                item.finding_id: item
                for item in (
                    *_config_findings(command),
                    *_migration_findings(command),
                    *_provenance_findings(command),
                )
            }.values(),
            key=lambda item: item.finding_id,
        )
    )
    actions = [
        ("verify_candidate", False),
        ("discover_provider_capabilities", False),
        ("validate_environment_config", False),
        ("verify_artifact_digest", False),
        ("verify_migration_preconditions", False),
        ("capture_prior_deployment", False),
        ("prepare_recovery", False),
        ("authorize_execution", False),
    ]
    if command.migration_plan is not None:
        actions.append(("execute_application_migrations", True))
    actions.extend(
        (
            ("deploy_artifact", True),
            ("wait_provider_readiness", False),
            ("post_deploy_verification", False),
            ("reconcile", False),
            ("runtime_approval", False),
        )
    )
    steps = tuple(
        DeploymentStep(
            semantic_id("DPS", {"candidate": candidate.candidate_id, "action": action}),
            index,
            action,
            mutating,
        )
        for index, (action, mutating) in enumerate(actions, 1)
    )
    plan = DeploymentPlan(
        CURRENT_WEB_CONTRACT_VERSION,
        semantic_id(
            "DPL",
            {
                "candidate": candidate,
                "target": command.target,
                "strategy": command.strategy,
                "steps": steps,
            },
        ),
        candidate.canonical_fingerprint(),
        command.target.canonical_fingerprint(),
        command.config.canonical_fingerprint(),
        command.provider.canonical_fingerprint(),
        command.provider.adapter_identity,
        command.artifacts[0].digest,
        command.strategy,
        None if command.migration_plan is None else command.migration_plan.canonical_fingerprint(),
        command.rollback_plan,
        steps,
    )
    review = ReleaseReviewPackage(
        semantic_id("RRP", {"candidate": candidate, "plan": plan, "findings": findings}),
        candidate.canonical_fingerprint(),
        plan.canonical_fingerprint(),
        findings,
        ReleaseReadiness.BLOCKED if findings else ReleaseReadiness.READY_FOR_EXECUTION,
    )
    return PrepareReleaseResult(candidate, plan, review)


def authorize_deployment(command: AuthorizeDeploymentCommand) -> AuthorizeDeploymentResult:
    prepared = command.prepared
    if prepared.review.readiness is not ReleaseReadiness.READY_FOR_EXECUTION:
        raise DeploymentAuthorizationError("Blocking release findings prevent execution")
    if prepared.plan.environment_fingerprint != command.target.canonical_fingerprint():
        raise DeploymentAuthorizationError("Deployment target changed after planning")
    if prepared.plan.provider_profile_fingerprint != command.provider.canonical_fingerprint():
        raise DeploymentAuthorizationError("Provider profile changed after planning")
    migration_fingerprint = (
        None if command.migration_plan is None else command.migration_plan.canonical_fingerprint()
    )
    if migration_fingerprint != prepared.plan.migration_plan_fingerprint:
        raise DeploymentAuthorizationError("Migration plan changed after planning")
    required_reviews = 2 if prepared.candidate.route is WebRoute.CRITICAL else 1
    if len({item.evidence_id for item in command.reviewer_evidence}) < required_reviews:
        raise DeploymentAuthorizationError("Route-specific execution approval is missing")
    authorization = DeploymentExecutionAuthorization(
        semantic_id(
            "DEA",
            {
                "execution": command.execution_id,
                "plan": prepared.plan,
                "reviews": command.reviewer_evidence,
            },
        ),
        command.execution_id,
        prepared.candidate.canonical_fingerprint(),
        prepared.plan.canonical_fingerprint(),
        command.target.environment_id,
        command.provider.profile_id,
        prepared.plan.artifact_digest,
        migration_fingerprint,
        command.expected_prior_deployment_ref,
        command.reviewer_evidence,
        True,
    )
    return AuthorizeDeploymentResult(authorization)


def execute_deployment(
    command: ExecuteDeploymentCommand, provider: DeploymentProviderPort
) -> ExecuteDeploymentResult:
    authorization, plan = command.authorization, command.prepared.plan
    if not authorization.authorized:
        raise DeploymentAuthorizationError("Deployment is not authorized")
    if provider.identity != plan.provider_adapter_identity:
        raise DeploymentExecutionError("Provider adapter identity changed after planning")
    exact = (
        authorization.candidate_fingerprint == command.prepared.candidate.canonical_fingerprint(),
        authorization.plan_fingerprint == plan.canonical_fingerprint(),
        authorization.environment_id == command.target.environment_id,
        plan.environment_fingerprint == command.target.canonical_fingerprint(),
        authorization.artifact_digest == command.artifact.digest == plan.artifact_digest,
        plan.config_fingerprint == command.config.canonical_fingerprint(),
    )
    if not all(exact):
        raise DeploymentExecutionError("Authorized deployment inputs changed")
    receipt = provider.deploy(
        authorization, plan, command.artifact, command.target, command.migration_plan
    )
    if (
        receipt.execution_id != authorization.execution_id
        or receipt.plan_fingerprint != plan.canonical_fingerprint()
    ):
        raise DeploymentExecutionError("Provider receipt is not bound to the authorized execution")
    if receipt.candidate_fingerprint != command.prepared.candidate.canonical_fingerprint():
        raise DeploymentExecutionError("Provider receipt candidate mismatch")
    return ExecuteDeploymentResult(receipt)


def verify_deployment(
    command: VerifyDeploymentCommand, provider: DeploymentProviderPort
) -> VerifyDeploymentResult:
    receipt, prepared = command.receipt, command.prepared
    if receipt.reconciliation_status is ReconciliationStatus.REQUIRED or receipt.outcome in {
        DeploymentOutcome.RECONCILIATION_REQUIRED,
        DeploymentOutcome.FAILED_NO_EXTERNAL_CHANGE,
        DeploymentOutcome.FAILED_ROLLED_BACK_VERIFIED,
    }:
        raise DeploymentVerificationError("Deployment state is not verifiable")
    if receipt.endpoint is None or receipt.observed_artifact_digest is None:
        raise DeploymentVerificationError("Provider receipt lacks observable deployment evidence")
    if (
        receipt.candidate_fingerprint != prepared.candidate.canonical_fingerprint()
        or receipt.artifact_digest != prepared.plan.artifact_digest
    ):
        raise DeploymentVerificationError("Deployment receipt is stale")
    checks = ("artifact", "backend", "health", "mock_leakage", "security", "smoke", "tls")
    plan = PostDeployVerificationPlan(
        semantic_id("PVP", {"receipt": receipt, "checks": checks}),
        prepared.candidate.canonical_fingerprint(),
        receipt.canonical_fingerprint(),
        prepared.plan.artifact_digest,
        command.target.health_path,
        checks,
    )
    evidence = provider.verify(plan, receipt, command.target)
    if (
        evidence.plan_fingerprint != plan.canonical_fingerprint()
        or evidence.receipt_fingerprint != receipt.canonical_fingerprint()
    ):
        raise DeploymentVerificationError("Post-deployment evidence is stale")
    if evidence.observed_artifact_digest != prepared.plan.artifact_digest or not evidence.passed:
        raise DeploymentVerificationError("Post-deployment verification failed")
    return VerifyDeploymentResult(plan, evidence)


__all__ = ("authorize_deployment", "execute_deployment", "prepare_release", "verify_deployment")
