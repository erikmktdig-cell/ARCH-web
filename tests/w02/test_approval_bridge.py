"""Approval validation and public Runtime delegation tests."""

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
    ApproveRequirementsCommand,
    EvidenceRef,
    PrepareRequirementsCommand,
    RequirementsApprovalError,
    RequirementsConflictError,
    RequirementsIncompleteError,
    RequirementsReadiness,
    WebLifecycleStatus,
    WebRoute,
    approve_requirements,
    prepare_requirements,
)
from w02.factories import PROJECT_ID, REQUEST_ID, intake


def _runtime_result(success: bool) -> ApplyTransitionResult:
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
                    "Conflicting request",
                    operation="test.apply_transition",
                    remediation="use a new key",
                    project_id=command.project_id,
                )
            return previous[1]
        self.commands.append(command)
        self.completed[command.idempotency_key] = (payload, self.result)
        return self.result


def approval_command(**changes: object) -> ApproveRequirementsCommand:
    prepared = prepare_requirements(PrepareRequirementsCommand(intake()))
    values: dict[str, object] = {
        "project_id": PROJECT_ID,
        "project_status": WebLifecycleStatus.DRAFT,
        "prepared": prepared,
        "expected_requirements_fingerprint": prepared.requirements_contract.canonical_fingerprint(),
        "expected_review_fingerprint": prepared.review_package.canonical_fingerprint(),
        "approval_evidence": EvidenceRef("approval-1", "human-approval", "urn:approval:1"),
        "idempotency_key": "web:requirements:approve:1",
        "request_id": REQUEST_ID,
        "transition_key": "web.requirements_approve",
        "expected_runtime_state": "not_started",
        "expected_record_version": 1,
        "expected_record_fingerprint": f"sha256:{'a' * 64}",
        "expected_content_fingerprint": f"sha256:{'b' * 64}",
        "actor_id": "user:reviewer",
        "actor_display_name": "Reviewer",
    }
    values.update(changes)
    return ApproveRequirementsCommand(**values)  # type: ignore[arg-type]


def test_successful_runtime_acceptance_is_the_only_approved_state() -> None:
    fake = FakeRuntime(_runtime_result(True))
    result = approve_requirements(cast(Runtime, fake), approval_command())
    assert result.approved
    assert result.readiness is RequirementsReadiness.APPROVED
    sent = fake.commands[0]
    assert sent.transition_key == "web.requirements_approve"
    metadata = sent.metadata
    assert metadata["web_transition"] == "DRAFT->REQUIREMENTS_APPROVED"
    assert metadata["selected_route"] == "quick"
    assert metadata["product_brief_fingerprint"]
    assert metadata["requirements_contract_fingerprint"]
    assert metadata["review_package_fingerprint"]
    assert metadata["approval_evidence_ref"]


def test_runtime_rejection_is_preserved_as_not_approved() -> None:
    fake = FakeRuntime(_runtime_result(False))
    result = approve_requirements(cast(Runtime, fake), approval_command())
    assert not result.approved
    assert result.readiness is RequirementsReadiness.READY_FOR_REVIEW
    assert result.runtime_result is fake.result


def test_exact_idempotency_replay_returns_same_runtime_evidence() -> None:
    fake = FakeRuntime(_runtime_result(True))
    command = approval_command()
    first = approve_requirements(cast(Runtime, fake), command)
    second = approve_requirements(cast(Runtime, fake), command)
    assert first == second
    assert len(fake.commands) == 1


def test_conflicting_idempotency_request_is_not_intercepted() -> None:
    fake = FakeRuntime(_runtime_result(True))
    command = approval_command()
    approve_requirements(cast(Runtime, fake), command)
    changed = replace(command, actor_display_name="Different reviewer")
    with pytest.raises(IdempotencyConflictError):
        approve_requirements(cast(Runtime, fake), changed)


@pytest.mark.parametrize("error_type", [ConcurrentModificationError, PersistenceError])
def test_runtime_errors_propagate_unchanged(
    error_type: type[ConcurrentModificationError] | type[PersistenceError],
) -> None:
    fake = FakeRuntime(_runtime_result(True))
    error = error_type(
        "Stale aggregate",
        operation="test.apply_transition",
        remediation="reload",
    )
    fake.error = error
    with pytest.raises(error_type) as captured:
        approve_requirements(cast(Runtime, fake), approval_command())
    assert captured.value is error


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"project_status": WebLifecycleStatus.IMPLEMENTING}, "DRAFT"),
        ({"project_id": "PRJ-01HZX7M3FQ1T2Q9V8Y6K4C2B1C"}, "identity"),
        ({"expected_requirements_fingerprint": "0" * 64}, "Requirements fingerprint"),
        ({"expected_review_fingerprint": "0" * 64}, "Review fingerprint"),
    ],
)
def test_approval_bindings_fail_closed(changes: dict[str, object], message: str) -> None:
    with pytest.raises(RequirementsApprovalError, match=message):
        approve_requirements(
            cast(Runtime, FakeRuntime(_runtime_result(True))), approval_command(**changes)
        )


def test_blocking_gap_prevents_runtime_call() -> None:
    prepared = prepare_requirements(PrepareRequirementsCommand(intake(primary_goal="")))
    command = approval_command(
        prepared=prepared,
        expected_requirements_fingerprint=prepared.requirements_contract.canonical_fingerprint(),
        expected_review_fingerprint=prepared.review_package.canonical_fingerprint(),
    )
    fake = FakeRuntime(_runtime_result(True))
    with pytest.raises(RequirementsIncompleteError):
        approve_requirements(cast(Runtime, fake), command)
    assert fake.commands == []


def test_conflict_prevents_runtime_call() -> None:
    prepared = prepare_requirements(
        PrepareRequirementsCommand(
            intake(
                core_capabilities=("Public access",),
                auth_security_needs=("Mandatory authentication",),
            )
        )
    )
    command = approval_command(
        prepared=prepared,
        expected_requirements_fingerprint=prepared.requirements_contract.canonical_fingerprint(),
        expected_review_fingerprint=prepared.review_package.canonical_fingerprint(),
    )
    with pytest.raises(RequirementsConflictError):
        approve_requirements(cast(Runtime, FakeRuntime(_runtime_result(True))), command)


def test_invalid_command_version_and_identifiers_fail_before_runtime() -> None:
    with pytest.raises(ValueError, match="positive"):
        approval_command(expected_record_version=0)
    invalid = approval_command(project_id="not-a-kernel-project-id")
    with pytest.raises(ValueError, match="identity"):
        approve_requirements(cast(Runtime, FakeRuntime(_runtime_result(True))), invalid)


def test_recommendation_cannot_override_selected_route_in_metadata() -> None:
    prepared = prepare_requirements(
        PrepareRequirementsCommand(
            intake(WebRoute.QUICK, auth_security_needs=("Financial security-critical data",))
        )
    )
    command = approval_command(
        prepared=prepared,
        expected_requirements_fingerprint=prepared.requirements_contract.canonical_fingerprint(),
        expected_review_fingerprint=prepared.review_package.canonical_fingerprint(),
    )
    fake = FakeRuntime(_runtime_result(True))
    approve_requirements(cast(Runtime, fake), command)
    assert fake.commands[0].metadata["selected_route"] == "quick"
