"""Public Runtime bridge for implementation-readiness approval."""

from __future__ import annotations

from arch_kernel.contracts import ChangeId, ProjectId, TransitionDomain, TransitionTarget
from arch_runtime import ApplyTransitionCommand, Runtime

from arch_web.application.workspace.errors import ImplementationReadinessApprovalError
from arch_web.application.workspace.models import (
    ApproveImplementationReadinessCommand,
    ApproveImplementationReadinessResult,
)
from arch_web.domain.enums import WebLifecycleStatus
from arch_web.domain.workspace import (
    ExecutionOutcome,
    ReconciliationStatus,
    WorkspaceReadiness,
)


def approve_implementation_readiness(
    runtime: Runtime, command: ApproveImplementationReadinessCommand
) -> ApproveImplementationReadinessResult:
    prepared = command.prepared
    receipt = command.receipt
    if command.project_status is not WebLifecycleStatus.UI_APPROVED:
        raise ImplementationReadinessApprovalError("Approval requires UI_APPROVED")
    if {
        command.project_id,
        prepared.plan.project_id,
        prepared.stack.project_id,
        receipt.project_id,
    } != {command.project_id}:
        raise ImplementationReadinessApprovalError("Implementation-readiness identity mismatch")
    bindings = (
        (
            prepared.plan.requirements_ref.fingerprint,
            command.expected_requirements_fingerprint,
            "Requirements",
        ),
        (
            prepared.plan.architecture_ref.fingerprint,
            command.expected_architecture_fingerprint,
            "Architecture",
        ),
        (
            prepared.plan.design_system_ref.fingerprint,
            command.expected_design_system_fingerprint,
            "Design system",
        ),
        (
            prepared.plan.ui_specification_ref.fingerprint,
            command.expected_ui_specification_fingerprint,
            "UI specification",
        ),
        (
            prepared.plan.ui_review_ref.fingerprint,
            command.expected_ui_review_fingerprint,
            "UI review",
        ),
        (prepared.stack.canonical_fingerprint(), command.expected_stack_fingerprint, "Stack"),
        (
            prepared.plan.canonical_fingerprint(),
            command.expected_plan_fingerprint,
            "Implementation plan",
        ),
        (
            prepared.change_set.canonical_fingerprint(),
            command.expected_change_set_fingerprint,
            "Change set",
        ),
        (
            receipt.canonical_fingerprint(),
            command.expected_receipt_fingerprint,
            "Execution receipt",
        ),
    )
    for actual, expected, label in bindings:
        if actual != expected:
            raise ImplementationReadinessApprovalError(f"{label} fingerprint is stale")
    if prepared.review.readiness is not WorkspaceReadiness.READY_FOR_REVIEW:
        raise ImplementationReadinessApprovalError("Workspace review is not ready")
    if any(item.blocking for item in prepared.review.findings):
        raise ImplementationReadinessApprovalError("Blocking workspace findings remain")
    if receipt.outcome not in {ExecutionOutcome.APPLIED, ExecutionOutcome.NOOP_ALREADY_SATISFIED}:
        raise ImplementationReadinessApprovalError("Workspace execution is not successful")
    if receipt.reconciliation_status is not ReconciliationStatus.CLEAN:
        raise ImplementationReadinessApprovalError("Workspace requires reconciliation")
    if not receipt.repository_evidence.clean_after:
        raise ImplementationReadinessApprovalError(
            "Repository is unexpectedly dirty after execution"
        )
    if receipt.change_set_fingerprint != prepared.change_set.canonical_fingerprint():
        raise ImplementationReadinessApprovalError("Receipt does not bind the approved change set")

    metadata = {
        "web_transition": "UI_APPROVED->IMPLEMENTATION_READY",
        "requirements_fingerprint": command.expected_requirements_fingerprint,
        "architecture_fingerprint": command.expected_architecture_fingerprint,
        "design_system_fingerprint": command.expected_design_system_fingerprint,
        "ui_specification_fingerprint": command.expected_ui_specification_fingerprint,
        "ui_review_fingerprint": command.expected_ui_review_fingerprint,
        "resolved_stack_fingerprint": command.expected_stack_fingerprint,
        "implementation_plan_fingerprint": command.expected_plan_fingerprint,
        "workspace_change_set_fingerprint": command.expected_change_set_fingerprint,
        "execution_receipt_fingerprint": command.expected_receipt_fingerprint,
        "post_tree_fingerprint": receipt.post_tree_fingerprint,
        "git_head": receipt.repository_evidence.after_head,
        "execution_outcome": receipt.outcome.value,
        "reconciliation_status": receipt.reconciliation_status.value,
        "blocking_finding_count": 0,
        "approval_evidence_ref": command.approval_evidence.canonical_data(),
        "contract_versions": {
            "stack": prepared.stack.contract_version,
            "plan": prepared.plan.contract_version,
            "change_set": prepared.change_set.contract_version,
            "receipt": receipt.contract_version,
            "review": prepared.review.contract_version,
        },
    }
    runtime_command = ApplyTransitionCommand.model_validate(
        {
            "idempotency_key": command.idempotency_key,
            "project_id": ProjectId(command.project_id),
            "request_id": ChangeId(command.request_id),
            "target": TransitionTarget(
                domain=TransitionDomain.PROJECT_LIFECYCLE, entity_id=ProjectId(command.project_id)
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
    return ApproveImplementationReadinessResult(
        command.project_id,
        approved,
        WorkspaceReadiness.APPROVED if approved else WorkspaceReadiness.READY_FOR_REVIEW,
        runtime_result,
    )


__all__ = ("approve_implementation_readiness",)
