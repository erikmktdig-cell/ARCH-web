"""Public Runtime bridge for governed UI specification approval."""

from __future__ import annotations

from arch_runtime import Runtime

from arch_web.application.design.errors import UIDesignApprovalError
from arch_web.application.design.models import (
    ApproveUISpecificationCommand,
    ApproveUISpecificationResult,
)
from arch_web.domain.enums import WebLifecycleStatus
from arch_web.domain.ui_review import UIReadiness
from arch_web.runtime_bridge.runtime_metadata import build_runtime_metadata
from arch_web.runtime_bridge.workflow import (
    WebWorkflowAuthorityError,
    build_web_transition_command,
)


def approve_ui_specification(
    runtime: Runtime, command: ApproveUISpecificationCommand
) -> ApproveUISpecificationResult:
    prepared = command.prepared
    review = prepared.review_package
    project_ids = {
        prepared.design_intent.project_id,
        prepared.design_system.project_id,
        prepared.ui_specification.project_id,
        prepared.coverage.project_id,
        review.project_id,
    }
    if project_ids != {command.project_id}:
        raise UIDesignApprovalError("UI approval project identity mismatch")
    profile_actual = (
        None if review.selected_profile_ref is None else review.selected_profile_ref.fingerprint
    )
    bindings = (
        (
            review.requirements_ref.fingerprint,
            command.expected_requirements_fingerprint,
            "Requirements",
        ),
        (
            review.architecture_ref.fingerprint,
            command.expected_architecture_fingerprint,
            "Architecture",
        ),
        (
            prepared.design_intent.canonical_fingerprint(),
            command.expected_design_intent_fingerprint,
            "Design intent",
        ),
        (profile_actual, command.expected_profile_fingerprint, "Design profile"),
        (
            prepared.design_system.canonical_fingerprint(),
            command.expected_design_system_fingerprint,
            "Design system",
        ),
        (
            prepared.ui_specification.canonical_fingerprint(),
            command.expected_ui_specification_fingerprint,
            "UI specification",
        ),
        (
            prepared.coverage.canonical_fingerprint(),
            command.expected_coverage_fingerprint,
            "Coverage",
        ),
        (review.canonical_fingerprint(), command.expected_review_fingerprint, "UI review"),
    )
    for actual, expected, label in bindings:
        if actual != expected:
            raise UIDesignApprovalError(f"{label} fingerprint is stale")
    review.design_intent_ref.verify(prepared.design_intent, prepared.design_intent.design_intent_id)
    review.design_system_ref.verify(prepared.design_system, prepared.design_system.contract_id)
    review.ui_specification_ref.verify(
        prepared.ui_specification, prepared.ui_specification.contract_id
    )
    review.coverage_ref.verify(prepared.coverage, prepared.coverage.coverage_id)
    if review.readiness is not UIReadiness.READY_FOR_REVIEW:
        raise UIDesignApprovalError("UI specification is not ready for explicit approval")
    if any(item.blocking for item in review.findings):
        raise UIDesignApprovalError("Blocking UI design findings remain")

    metadata = build_runtime_metadata(
        strings={
            "web_transition": "ARCHITECTURE_APPROVED->UI_APPROVED",
            "requirements_fingerprint": command.expected_requirements_fingerprint,
            "architecture_fingerprint": command.expected_architecture_fingerprint,
            "design_intent_fingerprint": prepared.design_intent.canonical_fingerprint(),
            "design_profile_fingerprint": profile_actual,
            "design_system_fingerprint": prepared.design_system.canonical_fingerprint(),
            "ui_specification_fingerprint": prepared.ui_specification.canonical_fingerprint(),
            "coverage_fingerprint": prepared.coverage.canonical_fingerprint(),
            "ui_review_fingerprint": review.canonical_fingerprint(),
            "selected_route": review.route.value,
        },
        integers={
            "blocking_finding_count": 0,
            "unresolved_non_blocking_count": sum(
                1 for item in review.findings if not item.blocking
            ),
        },
        structured={
            "approval_evidence_ref": command.approval_evidence.canonical_data(),
            "contract_versions": {
                "design_system": prepared.design_system.contract_version,
                "ui_specification": prepared.ui_specification.contract_version,
                "coverage": prepared.coverage.contract_version,
                "review": review.contract_version,
            },
        },
    )
    try:
        runtime_command = build_web_transition_command(
            runtime,
            project_id=command.project_id,
            asserted_status=command.project_status,
            asserted_runtime_state=command.expected_runtime_state,
            destination=WebLifecycleStatus.UI_APPROVED,
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
        raise UIDesignApprovalError(str(error)) from error
    runtime_result = runtime.apply_transition(runtime_command)
    approved = runtime_result.success
    return ApproveUISpecificationResult(
        project_id=command.project_id,
        approved=approved,
        readiness=UIReadiness.APPROVED if approved else UIReadiness.READY_FOR_REVIEW,
        runtime_result=runtime_result,
    )


__all__ = ("approve_ui_specification",)
