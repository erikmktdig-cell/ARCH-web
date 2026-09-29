"""Thin public-Runtime bridge for explicit architecture approval."""

from __future__ import annotations

from arch_runtime import Runtime

from arch_web.application.architecture.errors import ArchitectureApprovalError
from arch_web.application.architecture.models import (
    ApproveArchitectureCommand,
    ApproveArchitectureResult,
)
from arch_web.domain.architecture_review import ArchitectureReadiness
from arch_web.domain.enums import WebLifecycleStatus
from arch_web.runtime_bridge.runtime_metadata import build_runtime_metadata
from arch_web.runtime_bridge.workflow import (
    WebWorkflowAuthorityError,
    build_web_transition_command,
)


def approve_architecture(
    runtime: Runtime, command: ApproveArchitectureCommand
) -> ApproveArchitectureResult:
    prepared = command.prepared
    architecture = prepared.information_architecture
    navigation = prepared.navigation_model
    review = prepared.review_package
    if {architecture.project_id, navigation.project_id, review.project_id} != {command.project_id}:
        raise ArchitectureApprovalError("Architecture project identity mismatch")
    bindings = (
        (
            review.requirements_contract_ref.fingerprint,
            command.expected_requirements_fingerprint,
            "Requirements",
        ),
        (
            architecture.canonical_fingerprint(),
            command.expected_architecture_fingerprint,
            "Architecture",
        ),
        (
            navigation.canonical_fingerprint(),
            command.expected_navigation_fingerprint,
            "Navigation",
        ),
        (review.canonical_fingerprint(), command.expected_review_fingerprint, "Review"),
    )
    for actual, expected, label in bindings:
        if actual != expected:
            raise ArchitectureApprovalError(f"{label} fingerprint is stale")
    review.information_architecture_ref.verify(architecture, architecture.contract_id)
    review.navigation_model_ref.verify(navigation, navigation.navigation_id)
    if review.readiness is not ArchitectureReadiness.READY_FOR_REVIEW:
        raise ArchitectureApprovalError("Architecture is not ready for explicit approval")
    if any(item.blocking for item in review.findings):
        raise ArchitectureApprovalError("Blocking architecture findings remain")

    metadata = build_runtime_metadata(
        strings={
            "web_transition": "REQUIREMENTS_APPROVED->ARCHITECTURE_APPROVED",
            "requirements_contract_fingerprint": command.expected_requirements_fingerprint,
            "information_architecture_fingerprint": architecture.canonical_fingerprint(),
            "navigation_model_fingerprint": navigation.canonical_fingerprint(),
            "architecture_review_fingerprint": review.canonical_fingerprint(),
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
                "requirements": review.requirements_contract_ref.contract_version,
                "architecture": architecture.contract_version,
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
            destination=WebLifecycleStatus.ARCHITECTURE_APPROVED,
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
        raise ArchitectureApprovalError(str(error)) from error
    runtime_result = runtime.apply_transition(runtime_command)
    approved = runtime_result.success
    return ApproveArchitectureResult(
        project_id=command.project_id,
        approved=approved,
        readiness=(
            ArchitectureReadiness.APPROVED if approved else ArchitectureReadiness.READY_FOR_REVIEW
        ),
        runtime_result=runtime_result,
    )


__all__ = ("approve_architecture",)
