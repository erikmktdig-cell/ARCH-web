"""Public Runtime approval bridge tests."""

from __future__ import annotations

from dataclasses import replace
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
    ApproveArchitectureCommand,
    ArchitectureApprovalError,
    ArchitectureReadiness,
    EvidenceRef,
    WebLifecycleStatus,
    approve_architecture,
    prepare_architecture,
)
from w02.factories import PROJECT_ID, REQUEST_ID
from w03.factories import architecture_command


def _result(success: bool) -> ApplyTransitionResult:
    return cast(ApplyTransitionResult, SimpleNamespace(success=success))


class FakeRuntime:
    def __init__(self, result: ApplyTransitionResult) -> None:
        self.result = result
        self.commands: list[ApplyTransitionCommand] = []
        self.completed: dict[str, tuple[dict[str, object], ApplyTransitionResult]] = {}
        self.error: Exception | None = None

    def apply_transition(self, command: ApplyTransitionCommand) -> ApplyTransitionResult:
        if self.error is not None:
            raise self.error
        payload = command.request_payload()
        previous = self.completed.get(command.idempotency_key)
        if previous is not None:
            if previous[0] != payload:
                raise IdempotencyConflictError("conflict", operation="test", remediation="new key")
            return previous[1]
        self.commands.append(command)
        self.completed[command.idempotency_key] = (payload, self.result)
        return self.result


def approval_command(**changes: object) -> ApproveArchitectureCommand:
    prepared = prepare_architecture(architecture_command())
    values: dict[str, object] = {
        "project_id": PROJECT_ID,
        "project_status": WebLifecycleStatus.REQUIREMENTS_APPROVED,
        "prepared": prepared,
        "expected_requirements_fingerprint": (
            prepared.review_package.requirements_contract_ref.fingerprint
        ),
        "expected_architecture_fingerprint": (
            prepared.information_architecture.canonical_fingerprint()
        ),
        "expected_navigation_fingerprint": prepared.navigation_model.canonical_fingerprint(),
        "expected_review_fingerprint": prepared.review_package.canonical_fingerprint(),
        "approval_evidence": EvidenceRef("approval-w03", "human-approval", "urn:approval:w03"),
        "idempotency_key": "web:architecture:approve:1",
        "request_id": REQUEST_ID,
        "transition_key": "web.architecture_approve",
        "expected_runtime_state": "not_started",
        "expected_record_version": 2,
        "expected_record_fingerprint": f"sha256:{'a' * 64}",
        "expected_content_fingerprint": f"sha256:{'b' * 64}",
        "actor_id": "user:architect",
        "actor_display_name": "Architect",
    }
    values.update(changes)
    return ApproveArchitectureCommand(**values)  # type: ignore[arg-type]


def test_success_and_rejection_preserve_runtime_authority() -> None:
    accepted = FakeRuntime(_result(True))
    result = approve_architecture(cast(Runtime, accepted), approval_command())
    assert result.approved
    assert result.readiness is ArchitectureReadiness.APPROVED
    metadata = accepted.commands[0].metadata
    assert metadata["web_transition"] == "REQUIREMENTS_APPROVED->ARCHITECTURE_APPROVED"
    assert metadata["blocking_finding_count"] == 0
    assert metadata["selected_route"] == "quick"
    rejected = approve_architecture(cast(Runtime, FakeRuntime(_result(False))), approval_command())
    assert not rejected.approved
    assert rejected.readiness is ArchitectureReadiness.READY_FOR_REVIEW


def test_exact_retry_is_idempotent_and_conflicting_retry_propagates() -> None:
    runtime = FakeRuntime(_result(True))
    command = approval_command()
    first = approve_architecture(cast(Runtime, runtime), command)
    second = approve_architecture(cast(Runtime, runtime), command)
    assert first == second
    assert len(runtime.commands) == 1
    with pytest.raises(IdempotencyConflictError):
        approve_architecture(cast(Runtime, runtime), replace(command, actor_display_name="Other"))


@pytest.mark.parametrize("error_type", [ConcurrentModificationError, PersistenceError])
def test_runtime_infrastructure_errors_propagate(error_type: type[Exception]) -> None:
    runtime = FakeRuntime(_result(True))
    runtime.error = error_type("failure", operation="test", remediation="retry")  # type: ignore[call-arg]
    with pytest.raises(error_type):
        approve_architecture(cast(Runtime, runtime), approval_command())


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("project_status", WebLifecycleStatus.DRAFT, "REQUIREMENTS_APPROVED"),
        ("project_id", "different", "identity"),
        ("expected_requirements_fingerprint", "0" * 64, "Requirements"),
        ("expected_architecture_fingerprint", "0" * 64, "Architecture"),
        ("expected_navigation_fingerprint", "0" * 64, "Navigation"),
        ("expected_review_fingerprint", "0" * 64, "Review"),
    ],
)
def test_approval_bindings_fail_before_runtime(field: str, value: object, message: str) -> None:
    runtime = FakeRuntime(_result(True))
    changed = replace(approval_command(), **{field: value})  # type: ignore[arg-type]
    with pytest.raises(ArchitectureApprovalError, match=message):
        approve_architecture(cast(Runtime, runtime), changed)
    assert runtime.commands == []


def test_not_ready_review_and_invalid_version_are_rejected() -> None:
    command = approval_command()
    review = replace(command.prepared.review_package, readiness=ArchitectureReadiness.NOT_READY)
    prepared = replace(command.prepared, review_package=review)
    command = replace(
        command,
        prepared=prepared,
        expected_review_fingerprint=review.canonical_fingerprint(),
    )
    with pytest.raises(ArchitectureApprovalError, match="not ready"):
        approve_architecture(cast(Runtime, FakeRuntime(_result(True))), command)
    with pytest.raises(ValueError, match="positive"):
        approval_command(expected_record_version=0)
