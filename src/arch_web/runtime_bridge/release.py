"""Public Runtime bridge for the governed RELEASE_READY to DEPLOYED transition."""

from __future__ import annotations

from arch_runtime import Runtime

from arch_web.application.architecture.planning import semantic_id
from arch_web.application.release.errors import DeploymentApprovalError
from arch_web.application.release.models import ApproveDeploymentCommand, ApproveDeploymentResult
from arch_web.contracts.versions import CURRENT_WEB_CONTRACT_VERSION
from arch_web.domain.enums import WebLifecycleStatus, WebRoute
from arch_web.domain.release import (
    DeploymentApprovalPackage,
    DeploymentOutcome,
    ReleaseReadiness,
)
from arch_web.domain.workspace import ReconciliationStatus
from arch_web.runtime_bridge.runtime_metadata import build_runtime_metadata
from arch_web.runtime_bridge.workflow import (
    WebWorkflowAuthorityError,
    build_web_transition_command,
)


def approve_deployment(
    runtime: Runtime, command: ApproveDeploymentCommand
) -> ApproveDeploymentResult:
    """Validate exact external evidence, then request the sole W09 Runtime transition."""
    prepared = command.prepared
    candidate = prepared.candidate
    plan = prepared.plan
    authorization = command.authorization
    receipt = command.receipt
    verification = command.verification
    if candidate.runtime_state is not WebLifecycleStatus.RELEASE_READY:
        raise DeploymentApprovalError("Release candidate is not frozen from RELEASE_READY")
    if prepared.review.readiness is not ReleaseReadiness.READY_FOR_EXECUTION:
        raise DeploymentApprovalError("Release review contains blockers")
    if not authorization.authorized or not command.approval_evidence:
        raise DeploymentApprovalError("Explicit deployment approvals are missing")
    required_reviews = 2 if candidate.route is WebRoute.CRITICAL else 1
    if len({item.evidence_id for item in command.approval_evidence}) < required_reviews:
        raise DeploymentApprovalError("Route-specific final approval is missing")
    if receipt.reconciliation_status is not ReconciliationStatus.CLEAN:
        raise DeploymentApprovalError("Deployment reconciliation is not clean")
    if receipt.outcome not in {
        DeploymentOutcome.APPLIED_PENDING_VERIFICATION,
        DeploymentOutcome.DEPLOYED_VERIFIED,
        DeploymentOutcome.NOOP_ALREADY_DEPLOYED,
    }:
        raise DeploymentApprovalError("Deployment receipt is not approvable")
    if not verification.evidence.passed:
        raise DeploymentApprovalError("Post-deployment verification did not pass")
    exact = (
        plan.candidate_fingerprint == candidate.canonical_fingerprint(),
        authorization.candidate_fingerprint == candidate.canonical_fingerprint(),
        authorization.plan_fingerprint == plan.canonical_fingerprint(),
        receipt.candidate_fingerprint == candidate.canonical_fingerprint(),
        receipt.plan_fingerprint == plan.canonical_fingerprint(),
        verification.plan.receipt_fingerprint == receipt.canonical_fingerprint(),
        verification.evidence.receipt_fingerprint == receipt.canonical_fingerprint(),
        verification.evidence.observed_artifact_digest == plan.artifact_digest,
        plan.environment_fingerprint == command.target.canonical_fingerprint(),
    )
    if not all(exact):
        raise DeploymentApprovalError("Final deployment evidence is stale")
    if (
        command.expected_record_version != candidate.runtime_record_version
        or command.expected_record_fingerprint != candidate.runtime_record_fingerprint
    ):
        raise DeploymentApprovalError("Runtime release candidate evidence is stale")
    package = DeploymentApprovalPackage(
        CURRENT_WEB_CONTRACT_VERSION,
        semantic_id(
            "DAP",
            {
                "candidate": candidate,
                "receipt": receipt,
                "verification": verification,
                "approvals": command.approval_evidence,
            },
        ),
        candidate.project_id,
        candidate.route,
        WebLifecycleStatus.RELEASE_READY,
        candidate.runtime_record_version,
        candidate.runtime_record_fingerprint,
        candidate.release_readiness.canonical_fingerprint(),
        candidate.canonical_fingerprint(),
        command.target.canonical_fingerprint(),
        plan.canonical_fingerprint(),
        authorization.canonical_fingerprint(),
        receipt.canonical_fingerprint(),
        verification.evidence.canonical_fingerprint(),
        plan.rollback_plan.canonical_fingerprint(),
        prepared.review.findings,
        ReconciliationStatus.CLEAN,
        command.approval_evidence,
        True,
    )
    metadata = build_runtime_metadata(
        strings={
            "web_transition": "RELEASE_READY->DEPLOYED",
            "release_candidate_fingerprint": candidate.canonical_fingerprint(),
            "release_readiness_fingerprint": candidate.release_readiness.canonical_fingerprint(),
            "deployment_plan_fingerprint": plan.canonical_fingerprint(),
            "deployment_authorization_fingerprint": authorization.canonical_fingerprint(),
            "deployment_receipt_fingerprint": receipt.canonical_fingerprint(),
            "post_deploy_verification_fingerprint": verification.evidence.canonical_fingerprint(),
            "deployment_approval_fingerprint": package.canonical_fingerprint(),
            "environment_id": command.target.environment_id,
            "provider_profile_id": receipt.provider_profile_id,
            "artifact_digest": receipt.artifact_digest,
            "reconciliation_status": receipt.reconciliation_status.value,
        },
        integers={"blocking_finding_count": 0},
        structured={
            "approval_evidence_refs": [item.canonical_data() for item in command.approval_evidence]
        },
    )
    try:
        runtime_command = build_web_transition_command(
            runtime,
            project_id=candidate.project_id,
            asserted_status=command.project_status,
            asserted_runtime_state=command.expected_runtime_state,
            destination=WebLifecycleStatus.DEPLOYED,
            transition_key=command.transition_key,
            idempotency_key=command.idempotency_key,
            request_id=command.request_id,
            expected_record_version=command.expected_record_version,
            expected_record_fingerprint=command.expected_record_fingerprint,
            expected_content_fingerprint=command.expected_content_fingerprint,
            expected_workflow_record_version=command.expected_workflow_record_version,
            expected_workflow_content_fingerprint=(command.expected_workflow_content_fingerprint),
            metadata=metadata,
            actor_id=command.actor_id,
            actor_display_name=command.actor_display_name,
        )
    except WebWorkflowAuthorityError as error:
        raise DeploymentApprovalError(str(error)) from error
    result = runtime.apply_transition(runtime_command)
    return ApproveDeploymentResult(package, result)


__all__ = ("approve_deployment",)
