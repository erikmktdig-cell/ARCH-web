"""Public Runtime bridges for governed W08 lifecycle transitions."""

from __future__ import annotations

from arch_runtime import ApplyTransitionCommand, Runtime

from arch_web.application.architecture.planning import semantic_id
from arch_web.application.qa.errors import QAApprovalError
from arch_web.application.qa.models import (
    ApproveReleaseReadinessCommand,
    ApproveReleaseReadinessResult,
    AuthorizeTestingCommand,
    AuthorizeTestingResult,
)
from arch_web.contracts.versions import CURRENT_WEB_CONTRACT_VERSION
from arch_web.domain.enums import WebLifecycleStatus
from arch_web.domain.qa import QAExecutionAuthorization, QAReadiness, ReleaseReadinessPackage
from arch_web.domain.workspace import ReconciliationStatus
from arch_web.runtime_bridge.runtime_metadata import build_runtime_metadata
from arch_web.runtime_bridge.workflow import (
    WebWorkflowAuthorityError,
    build_web_transition_command,
)


def _runtime_command(
    runtime: Runtime,
    command: AuthorizeTestingCommand | ApproveReleaseReadinessCommand,
    project_id: str,
    destination: WebLifecycleStatus,
    metadata: dict[str, str],
) -> ApplyTransitionCommand:
    return build_web_transition_command(
        runtime,
        project_id=project_id,
        asserted_status=command.project_status,
        asserted_runtime_state=command.expected_runtime_state,
        destination=destination,
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


def authorize_testing(runtime: Runtime, command: AuthorizeTestingCommand) -> AuthorizeTestingResult:
    candidate = command.prepared.candidate
    scope = command.prepared.scope
    if candidate.runtime_state is not WebLifecycleStatus.IMPLEMENTING:
        raise QAApprovalError("QA candidate is not frozen from IMPLEMENTING")
    if candidate.project_id != scope.project_id:
        raise QAApprovalError("QA authorization project identity mismatch")
    if candidate.canonical_fingerprint() != scope.candidate_fingerprint:
        raise QAApprovalError("QA scope does not bind the exact candidate")
    if candidate.qa_profile_fingerprint != scope.profile_fingerprint:
        raise QAApprovalError("QA scope does not bind the adopted profile")
    if (
        command.expected_record_version != candidate.runtime_record_version
        or command.expected_record_fingerprint != candidate.runtime_record_fingerprint
    ):
        raise QAApprovalError("QA candidate Runtime evidence is stale")
    metadata = build_runtime_metadata(
        strings={
            "web_transition": "IMPLEMENTING->TESTING",
            "qa_candidate_id": candidate.candidate_id,
            "qa_candidate_fingerprint": candidate.canonical_fingerprint(),
            "qa_scope_fingerprint": scope.canonical_fingerprint(),
            "qa_profile_fingerprint": candidate.qa_profile_fingerprint,
            "source_tree_fingerprint": candidate.source_tree_fingerprint,
            "git_head": candidate.git_head,
            "frontend_completion_fingerprint": candidate.frontend_completion_fingerprint,
            "backend_completion_fingerprint": candidate.backend_completion_fingerprint,
        },
        structured={"approval_evidence_ref": command.approval_evidence.canonical_data()},
    )
    try:
        runtime_command = _runtime_command(
            runtime,
            command,
            candidate.project_id,
            WebLifecycleStatus.TESTING,
            metadata,
        )
    except WebWorkflowAuthorityError as error:
        raise QAApprovalError(str(error)) from error
    result = runtime.apply_transition(runtime_command)
    authorization = QAExecutionAuthorization(
        CURRENT_WEB_CONTRACT_VERSION,
        semantic_id(
            "QAU",
            {
                "candidate": candidate.canonical_fingerprint(),
                "scope": scope.canonical_fingerprint(),
                "request": command.request_id,
                "authorized": result.success,
            },
        ),
        candidate.project_id,
        candidate.canonical_fingerprint(),
        scope.canonical_fingerprint(),
        candidate.qa_profile_fingerprint,
        WebLifecycleStatus.TESTING if result.success else WebLifecycleStatus.IMPLEMENTING,
        result.success,
    )
    return AuthorizeTestingResult(authorization, result)


def approve_release_readiness(
    runtime: Runtime, command: ApproveReleaseReadinessCommand
) -> ApproveReleaseReadinessResult:
    candidate = command.prepared.candidate
    scope = command.prepared.scope
    executed = command.executed
    review = executed.review
    if review.project_id != candidate.project_id or scope.project_id != candidate.project_id:
        raise QAApprovalError("Release-readiness project identity mismatch")
    bindings = (
        (review.candidate_ref.fingerprint, candidate.canonical_fingerprint(), "candidate"),
        (review.scope_ref.fingerprint, scope.canonical_fingerprint(), "scope"),
        (review.run_ref.fingerprint, executed.run.canonical_fingerprint(), "run"),
        (review.preview_ref.fingerprint, executed.preview.canonical_fingerprint(), "preview"),
        (
            review.coverage_matrix.canonical_fingerprint(),
            executed.coverage.canonical_fingerprint(),
            "coverage",
        ),
    )
    for actual, expected, label in bindings:
        if actual != expected:
            raise QAApprovalError(f"QA {label} evidence is stale")
    if review.readiness is not QAReadiness.READY_FOR_REVIEW:
        raise QAApprovalError("QA evidence is not ready for explicit approval")
    if any(item.blocking for item in review.findings):
        raise QAApprovalError("Blocking QA findings remain")
    if not executed.preview.cleanup_verified:
        raise QAApprovalError("Preview cleanup was not verified")
    if any(
        item.candidate_fingerprint != candidate.canonical_fingerprint()
        for item in executed.run.results
    ):
        raise QAApprovalError("QA run contains stale candidate evidence")
    package = ReleaseReadinessPackage(
        CURRENT_WEB_CONTRACT_VERSION,
        semantic_id(
            "RRP",
            {
                "candidate": candidate.canonical_fingerprint(),
                "review": review.canonical_fingerprint(),
                "approval": command.approval_evidence.canonical_fingerprint(),
            },
        ),
        candidate.project_id,
        WebLifecycleStatus.TESTING,
        candidate.canonical_fingerprint(),
        candidate.source_tree_fingerprint,
        candidate.git_head,
        candidate.qa_profile_fingerprint,
        scope.canonical_fingerprint(),
        executed.preview.canonical_fingerprint(),
        executed.run.canonical_fingerprint(),
        executed.coverage.canonical_fingerprint(),
        tuple(item.fingerprint for item in review.evidence_refs),
        review.findings,
        ReconciliationStatus.CLEAN,
        command.approval_evidence,
    )
    metadata = build_runtime_metadata(
        strings={
            "web_transition": "TESTING->RELEASE_READY",
            "qa_candidate_fingerprint": package.candidate_fingerprint,
            "qa_profile_fingerprint": package.profile_fingerprint,
            "qa_scope_fingerprint": package.scope_fingerprint,
            "qa_run_fingerprint": package.run_fingerprint,
            "qa_coverage_fingerprint": package.coverage_fingerprint,
            "release_readiness_fingerprint": package.canonical_fingerprint(),
            "source_tree_fingerprint": package.source_tree_fingerprint,
            "git_head": package.git_head,
        },
        integers={"blocking_finding_count": 0},
        structured={"approval_evidence_ref": command.approval_evidence.canonical_data()},
    )
    try:
        runtime_command = _runtime_command(
            runtime,
            command,
            candidate.project_id,
            WebLifecycleStatus.RELEASE_READY,
            metadata,
        )
    except WebWorkflowAuthorityError as error:
        raise QAApprovalError(str(error)) from error
    result = runtime.apply_transition(runtime_command)
    return ApproveReleaseReadinessResult(package, result)


__all__ = ("approve_release_readiness", "authorize_testing")
