"""Public Runtime bridge for governed W06 implementation authorization."""

from __future__ import annotations

from arch_runtime import Runtime

from arch_web.application.architecture.planning import semantic_id
from arch_web.application.frontend.errors import FrontendAuthorizationError
from arch_web.application.frontend.models import (
    AuthorizeFrontendCommand,
    AuthorizeFrontendResult,
)
from arch_web.contracts.versions import CURRENT_WEB_CONTRACT_VERSION
from arch_web.domain.enums import WebLifecycleStatus
from arch_web.domain.frontend import FrontendExecutionAuthorization
from arch_web.runtime_bridge.runtime_metadata import build_runtime_metadata
from arch_web.runtime_bridge.workflow import (
    WebWorkflowAuthorityError,
    build_web_transition_command,
)


def authorize_frontend(
    runtime: Runtime, command: AuthorizeFrontendCommand
) -> AuthorizeFrontendResult:
    assignment = command.prepared.assignment
    if assignment.canonical_fingerprint() != command.expected_assignment_fingerprint:
        raise FrontendAuthorizationError("Frontend assignment fingerprint is stale")
    if assignment.runtime_record_version != command.expected_record_version:
        raise FrontendAuthorizationError("Runtime record version is stale")
    if assignment.runtime_record_fingerprint != command.expected_record_fingerprint:
        raise FrontendAuthorizationError("Runtime record fingerprint is stale")
    metadata = build_runtime_metadata(
        strings={
            "web_transition": "IMPLEMENTATION_READY->IMPLEMENTING",
            "frontend_assignment_id": assignment.assignment_id,
            "frontend_assignment_fingerprint": assignment.canonical_fingerprint(),
            "implementation_plan_fingerprint": assignment.implementation_plan_fingerprint,
            "workspace_receipt_fingerprint": assignment.workspace_receipt_fingerprint,
            "managed_tree_fingerprint": assignment.managed_tree_fingerprint,
            "git_head": assignment.git_head,
        },
        integers={"blocking_finding_count": 0},
        structured={
            "selected_frontend_units": list(assignment.selected_unit_refs),
            "path_claims": list(assignment.path_claim_refs),
            "approval_evidence_ref": command.approval_evidence.canonical_data(),
        },
    )
    try:
        runtime_command = build_web_transition_command(
            runtime,
            project_id=assignment.project_id,
            asserted_status=command.project_status,
            asserted_runtime_state=command.expected_runtime_state,
            destination=WebLifecycleStatus.IMPLEMENTING,
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
        raise FrontendAuthorizationError(str(error)) from error
    result = runtime.apply_transition(runtime_command)
    authorization = FrontendExecutionAuthorization(
        CURRENT_WEB_CONTRACT_VERSION,
        semantic_id(
            "FAU",
            {
                "assignment": assignment.canonical_fingerprint(),
                "request": command.request_id,
                "authorized": result.success,
            },
        ),
        assignment.project_id,
        assignment.canonical_fingerprint(),
        assignment.implementation_plan_fingerprint,
        assignment.workspace_receipt_fingerprint,
        assignment.runtime_record_version,
        assignment.runtime_record_fingerprint,
        result.success,
    )
    return AuthorizeFrontendResult(authorization, result)


__all__ = ("authorize_frontend",)
