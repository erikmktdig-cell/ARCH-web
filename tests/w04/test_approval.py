"""Governed ARCHITECTURE_APPROVED to UI_APPROVED bridge tests."""

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
    ApproveUISpecificationCommand,
    EvidenceRef,
    UIDesignApprovalError,
    UIReadiness,
    WebLifecycleStatus,
    approve_ui_specification,
    prepare_ui_specification,
)
from w02.factories import PROJECT_ID, REQUEST_ID
from w04.factories import design_command


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
                raise IdempotencyConflictError(
                    "conflicting UI approval",
                    operation="test.ui.approval",
                    remediation="use a new idempotency key",
                )
            return previous[1]
        self.commands.append(command)
        self.completed[command.idempotency_key] = (payload, self.result)
        return self.result


def approval_command(**changes: object) -> ApproveUISpecificationCommand:
    prepared = prepare_ui_specification(design_command())
    profile_ref = prepared.review_package.selected_profile_ref
    values: dict[str, object] = {
        "project_id": PROJECT_ID,
        "project_status": WebLifecycleStatus.ARCHITECTURE_APPROVED,
        "prepared": prepared,
        "expected_requirements_fingerprint": prepared.review_package.requirements_ref.fingerprint,
        "expected_architecture_fingerprint": prepared.review_package.architecture_ref.fingerprint,
        "expected_design_intent_fingerprint": prepared.design_intent.canonical_fingerprint(),
        "expected_profile_fingerprint": None if profile_ref is None else profile_ref.fingerprint,
        "expected_design_system_fingerprint": prepared.design_system.canonical_fingerprint(),
        "expected_ui_specification_fingerprint": prepared.ui_specification.canonical_fingerprint(),
        "expected_coverage_fingerprint": prepared.coverage.canonical_fingerprint(),
        "expected_review_fingerprint": prepared.review_package.canonical_fingerprint(),
        "approval_evidence": EvidenceRef("approval-w04", "human-ui-approval", "urn:approval:w04"),
        "idempotency_key": "web:ui:approve:1",
        "request_id": REQUEST_ID,
        "transition_key": "web.ui_approve",
        "expected_runtime_state": "not_started",
        "expected_record_version": 3,
        "expected_record_fingerprint": f"sha256:{'a' * 64}",
        "expected_content_fingerprint": f"sha256:{'b' * 64}",
        "actor_id": "user:design-reviewer",
        "actor_display_name": "Design Reviewer",
    }
    values.update(changes)
    return ApproveUISpecificationCommand(**values)  # type: ignore[arg-type]


def test_runtime_acceptance_is_the_only_approved_state() -> None:
    runtime = FakeRuntime(_result(True))
    result = approve_ui_specification(cast(Runtime, runtime), approval_command())
    assert result.approved
    assert result.readiness is UIReadiness.APPROVED
    metadata = runtime.commands[0].metadata
    assert metadata["web_transition"] == "ARCHITECTURE_APPROVED->UI_APPROVED"
    assert metadata["selected_route"] == "quick"
    assert metadata["blocking_finding_count"] == 0
    assert metadata["requirements_fingerprint"]
    assert metadata["architecture_fingerprint"]
    assert metadata["design_system_fingerprint"]
    assert metadata["ui_specification_fingerprint"]


def test_runtime_domain_rejection_remains_not_approved() -> None:
    runtime = FakeRuntime(_result(False))
    result = approve_ui_specification(cast(Runtime, runtime), approval_command())
    assert not result.approved
    assert result.readiness is UIReadiness.READY_FOR_REVIEW
    assert result.runtime_result is runtime.result


def test_exact_retry_is_idempotent_and_changed_request_conflicts() -> None:
    runtime = FakeRuntime(_result(True))
    command = approval_command()
    first = approve_ui_specification(cast(Runtime, runtime), command)
    second = approve_ui_specification(cast(Runtime, runtime), command)
    assert first == second
    assert len(runtime.commands) == 1
    with pytest.raises(IdempotencyConflictError):
        approve_ui_specification(
            cast(Runtime, runtime), replace(command, actor_display_name="Other")
        )


@pytest.mark.parametrize("error_type", [ConcurrentModificationError, PersistenceError])
def test_runtime_errors_propagate_unchanged(error_type: type[Exception]) -> None:
    runtime = FakeRuntime(_result(True))
    runtime.error = error_type(
        "runtime failure", operation="test.ui.approval", remediation="reload"
    )  # type: ignore[call-arg]
    with pytest.raises(error_type) as captured:
        approve_ui_specification(cast(Runtime, runtime), approval_command())
    assert captured.value is runtime.error


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("project_status", WebLifecycleStatus.REQUIREMENTS_APPROVED, "ARCHITECTURE_APPROVED"),
        ("project_id", "different", "identity"),
        ("expected_requirements_fingerprint", "0" * 64, "Requirements"),
        ("expected_architecture_fingerprint", "0" * 64, "Architecture"),
        ("expected_design_intent_fingerprint", "0" * 64, "Design intent"),
        ("expected_profile_fingerprint", "0" * 64, "Design profile"),
        ("expected_design_system_fingerprint", "0" * 64, "Design system"),
        ("expected_ui_specification_fingerprint", "0" * 64, "UI specification"),
        ("expected_coverage_fingerprint", "0" * 64, "Coverage"),
        ("expected_review_fingerprint", "0" * 64, "UI review"),
    ],
)
def test_exact_approval_bindings_fail_before_runtime(
    field: str, value: object, message: str
) -> None:
    runtime = FakeRuntime(_result(True))
    changed = replace(approval_command(), **{field: value})  # type: ignore[arg-type]
    with pytest.raises(UIDesignApprovalError, match=message):
        approve_ui_specification(cast(Runtime, runtime), changed)
    assert runtime.commands == []


def test_not_ready_review_and_invalid_version_are_rejected() -> None:
    command = approval_command()
    review = replace(command.prepared.review_package, readiness=UIReadiness.NOT_READY)
    prepared = replace(command.prepared, review_package=review)
    changed = replace(
        command,
        prepared=prepared,
        expected_review_fingerprint=review.canonical_fingerprint(),
    )
    with pytest.raises(UIDesignApprovalError, match="not ready"):
        approve_ui_specification(cast(Runtime, FakeRuntime(_result(True))), changed)
    with pytest.raises(ValueError, match="positive"):
        approval_command(expected_record_version=0)
