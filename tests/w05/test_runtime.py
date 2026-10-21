"""Governed UI_APPROVED to IMPLEMENTATION_READY bridge tests."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from typing import cast

import pytest
from arch_runtime import (
    ApplyTransitionCommand,
    ApplyTransitionResult,
    ConcurrentModificationError,
    IdempotencyConflictError,
    PersistenceError,
    Runtime,
)

from arch_web import (
    ApplyWorkspaceCommand,
    ApproveImplementationReadinessCommand,
    EvidenceRef,
    ExecutionOutcome,
    ImplementationReadinessApprovalError,
    ReconciliationStatus,
    WebLifecycleStatus,
    WorkspaceExecutor,
    WorkspaceReadiness,
    approve_implementation_readiness,
    prepare_workspace,
)
from runtime_authority import runtime_project
from w02.factories import PROJECT_ID, REQUEST_ID
from w05.factories import workspace_command


def _runtime_result(success: bool) -> ApplyTransitionResult:
    return cast(ApplyTransitionResult, SimpleNamespace(success=success))


class FakeRuntime:
    def __init__(self, result: ApplyTransitionResult) -> None:
        self.result = result
        self.commands: list[ApplyTransitionCommand] = []
        self.completed: dict[str, tuple[dict[str, object], ApplyTransitionResult]] = {}
        self.error: Exception | None = None
        self.project = runtime_project(
            WebLifecycleStatus.UI_APPROVED,
            project_id=PROJECT_ID,
            record_version=4,
            record_fingerprint=f"sha256:{'a' * 64}",
            content_fingerprint=f"sha256:{'b' * 64}",
        )

    def get_project(self, project_id: object) -> object:
        return self.project

    def apply_transition(self, command: ApplyTransitionCommand) -> ApplyTransitionResult:
        if self.error is not None:
            raise self.error
        payload = command.request_payload()
        previous = self.completed.get(command.idempotency_key)
        if previous is not None:
            if previous[0] != payload:
                raise IdempotencyConflictError(
                    "conflicting readiness approval",
                    operation="test.workspace.approval",
                    remediation="use a new key",
                )
            return previous[1]
        self.commands.append(command)
        self.completed[command.idempotency_key] = (payload, self.result)
        return self.result


def approval_command(root: Path, **changes: object) -> ApproveImplementationReadinessCommand:
    source = workspace_command(root, new=True)
    prepared = prepare_workspace(source)
    receipt = (
        WorkspaceExecutor()
        .apply(ApplyWorkspaceCommand("execution:approval", source.target, prepared, source.policy))
        .receipt
    )
    values: dict[str, object] = {
        "project_id": PROJECT_ID,
        "project_status": WebLifecycleStatus.UI_APPROVED,
        "prepared": prepared,
        "receipt": receipt,
        "expected_requirements_fingerprint": prepared.plan.requirements_ref.fingerprint,
        "expected_architecture_fingerprint": prepared.plan.architecture_ref.fingerprint,
        "expected_design_system_fingerprint": prepared.plan.design_system_ref.fingerprint,
        "expected_ui_specification_fingerprint": prepared.plan.ui_specification_ref.fingerprint,
        "expected_ui_review_fingerprint": prepared.plan.ui_review_ref.fingerprint,
        "expected_stack_fingerprint": prepared.stack.canonical_fingerprint(),
        "expected_plan_fingerprint": prepared.plan.canonical_fingerprint(),
        "expected_change_set_fingerprint": prepared.change_set.canonical_fingerprint(),
        "expected_receipt_fingerprint": receipt.canonical_fingerprint(),
        "approval_evidence": EvidenceRef(
            "approval-w05", "human-readiness-approval", "urn:approval:w05"
        ),
        "idempotency_key": "web:implementation-ready:1",
        "request_id": REQUEST_ID,
        "transition_key": "web.implementation_ready",
        "expected_runtime_state": "UI_APPROVED",
        "expected_record_version": 4,
        "expected_record_fingerprint": f"sha256:{'a' * 64}",
        "expected_content_fingerprint": f"sha256:{'b' * 64}",
        "actor_id": "user:workspace-reviewer",
        "actor_display_name": "Workspace Reviewer",
    }
    values.update(changes)
    return ApproveImplementationReadinessCommand(**values)  # type: ignore[arg-type]


def test_runtime_is_only_implementation_ready_authority(tmp_path: Path) -> None:
    runtime = FakeRuntime(_runtime_result(True))
    result = approve_implementation_readiness(cast(Runtime, runtime), approval_command(tmp_path))
    assert result.approved
    assert result.readiness is WorkspaceReadiness.APPROVED
    metadata = runtime.commands[0].metadata
    assert metadata["web_transition"] == "UI_APPROVED->IMPLEMENTATION_READY"
    assert metadata["execution_outcome"] == "applied"
    assert metadata["blocking_finding_count"] == "0"


def test_runtime_domain_rejection_leaves_workspace_only_prepared(tmp_path: Path) -> None:
    runtime = FakeRuntime(_runtime_result(False))
    result = approve_implementation_readiness(cast(Runtime, runtime), approval_command(tmp_path))
    assert not result.approved
    assert result.readiness is WorkspaceReadiness.READY_FOR_REVIEW


def test_runtime_retry_is_exact_and_conflicting_request_fails(tmp_path: Path) -> None:
    runtime = FakeRuntime(_runtime_result(True))
    command = approval_command(tmp_path)
    assert approve_implementation_readiness(
        cast(Runtime, runtime), command
    ) == approve_implementation_readiness(cast(Runtime, runtime), command)
    assert len(runtime.commands) == 1
    with pytest.raises(IdempotencyConflictError):
        approve_implementation_readiness(
            cast(Runtime, runtime), replace(command, actor_display_name="Other")
        )


@pytest.mark.parametrize("error_type", [ConcurrentModificationError, PersistenceError])
def test_runtime_infrastructure_errors_propagate(
    tmp_path: Path, error_type: type[Exception]
) -> None:
    runtime = FakeRuntime(_runtime_result(True))
    runtime.error = error_type("runtime failure", operation="test", remediation="retry")  # type: ignore[call-arg]
    with pytest.raises(error_type):
        approve_implementation_readiness(cast(Runtime, runtime), approval_command(tmp_path))


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("project_status", WebLifecycleStatus.ARCHITECTURE_APPROVED, "Caller lifecycle"),
        ("project_id", "different", "identity"),
        ("expected_plan_fingerprint", "0" * 64, "plan"),
        ("expected_receipt_fingerprint", "0" * 64, "receipt"),
    ],
)
def test_approval_bindings_fail_before_runtime(
    tmp_path: Path, field: str, value: object, message: str
) -> None:
    runtime = FakeRuntime(_runtime_result(True))
    with pytest.raises(
        ImplementationReadinessApprovalError,
        match=message,
    ):
        approve_implementation_readiness(
            cast(Runtime, runtime),
            replace(approval_command(tmp_path), **{field: value}),  # type: ignore[arg-type]
        )
    assert not runtime.commands


def test_reconciliation_and_failed_execution_never_approve(tmp_path: Path) -> None:
    command = approval_command(tmp_path)
    receipt = replace(
        command.receipt,
        outcome=ExecutionOutcome.RECONCILIATION_REQUIRED,
        reconciliation_status=ReconciliationStatus.REQUIRED,
    )
    changed = replace(
        command, receipt=receipt, expected_receipt_fingerprint=receipt.canonical_fingerprint()
    )
    with pytest.raises(ImplementationReadinessApprovalError, match="successful"):
        approve_implementation_readiness(cast(Runtime, FakeRuntime(_runtime_result(True))), changed)


def test_not_ready_review_and_receipt_binding_never_approve(tmp_path: Path) -> None:
    command = approval_command(tmp_path)
    blocked_review = replace(command.prepared.review, readiness=WorkspaceReadiness.NOT_READY)
    blocked = replace(command, prepared=replace(command.prepared, review=blocked_review))
    with pytest.raises(ImplementationReadinessApprovalError, match="not ready"):
        approve_implementation_readiness(cast(Runtime, FakeRuntime(_runtime_result(True))), blocked)

    stale_receipt = replace(command.receipt, change_set_fingerprint="sha256:" + "0" * 64)
    stale = replace(
        command,
        receipt=stale_receipt,
        expected_receipt_fingerprint=stale_receipt.canonical_fingerprint(),
    )
    with pytest.raises(ImplementationReadinessApprovalError, match="bind"):
        approve_implementation_readiness(cast(Runtime, FakeRuntime(_runtime_result(True))), stale)
