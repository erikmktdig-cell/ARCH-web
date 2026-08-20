"""Thin public-Runtime bridge for explicit requirements approval."""

from __future__ import annotations

from arch_kernel.contracts import (
    ChangeId,
    ProjectId,
    TransitionDomain,
    TransitionTarget,
)
from arch_runtime import ApplyTransitionCommand, Runtime

from arch_web.application.requirements.errors import (
    RequirementsApprovalError,
    RequirementsConflictError,
    RequirementsIncompleteError,
)
from arch_web.application.requirements.models import (
    ApproveRequirementsCommand,
    ApproveRequirementsResult,
)
from arch_web.domain.enums import WebLifecycleStatus
from arch_web.domain.requirements_review import FindingSeverity, RequirementsReadiness


def approve_requirements(
    runtime: Runtime, command: ApproveRequirementsCommand
) -> ApproveRequirementsResult:
    prepared = command.prepared
    brief = prepared.product_brief
    requirements = prepared.requirements_contract
    review = prepared.review_package
    if command.project_status is not WebLifecycleStatus.DRAFT:
        raise RequirementsApprovalError("Requirements approval requires web DRAFT status")
    if {brief.project_id, requirements.project_id, review.project_id} != {command.project_id}:
        raise RequirementsApprovalError("Approval project identity mismatch")
    if requirements.canonical_fingerprint() != command.expected_requirements_fingerprint:
        raise RequirementsApprovalError("Requirements fingerprint is stale")
    if review.canonical_fingerprint() != command.expected_review_fingerprint:
        raise RequirementsApprovalError("Review fingerprint is stale")
    review.product_brief_ref.verify(brief, brief.brief_id)
    review.requirements_contract_ref.verify(requirements, requirements.contract_id)
    if review.gap_findings and any(
        item.severity is FindingSeverity.BLOCKING for item in review.gap_findings
    ):
        raise RequirementsIncompleteError("Blocking requirement gaps remain")
    if review.conflict_findings:
        raise RequirementsConflictError("Requirement conflicts remain")
    if review.readiness is not RequirementsReadiness.READY_FOR_REVIEW:
        raise RequirementsApprovalError("Review package is not ready for explicit approval")
    if brief.route is not requirements.route:
        raise RequirementsApprovalError("Authoritative route mismatch")

    metadata = {
        "web_transition": "DRAFT->REQUIREMENTS_APPROVED",
        "product_brief_fingerprint": brief.canonical_fingerprint(),
        "requirements_contract_fingerprint": requirements.canonical_fingerprint(),
        "review_package_fingerprint": review.canonical_fingerprint(),
        "approval_evidence_ref": command.approval_evidence.canonical_data(),
        "selected_route": brief.route.value,
        "unresolved_items": {
            "count": len(review.unresolved_items),
            "status": "resolved" if not review.unresolved_items else "visible",
        },
        "contract_version": requirements.contract_version,
    }
    runtime_command = ApplyTransitionCommand.model_validate(
        {
            "idempotency_key": command.idempotency_key,
            "project_id": ProjectId(command.project_id),
            "request_id": ChangeId(command.request_id),
            "target": TransitionTarget(
                domain=TransitionDomain.PROJECT_LIFECYCLE,
                entity_id=ProjectId(command.project_id),
            ),
            "transition_key": command.transition_key,
            "expected_from_state": command.expected_runtime_state,
            "expected_record_version": command.expected_record_version,
            "expected_record_fingerprint": command.expected_record_fingerprint,
            "expected_content_fingerprint": command.expected_content_fingerprint,
            "metadata": metadata,
            "actor_id": command.actor_id,
            "actor_display_name": command.actor_display_name,
        },
        strict=True,
    )
    runtime_result = runtime.apply_transition(runtime_command)
    approved = runtime_result.success
    return ApproveRequirementsResult(
        project_id=command.project_id,
        approved=approved,
        readiness=(
            RequirementsReadiness.APPROVED if approved else RequirementsReadiness.READY_FOR_REVIEW
        ),
        runtime_result=runtime_result,
    )


__all__ = ("approve_requirements",)
