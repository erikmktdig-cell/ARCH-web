"""Runtime-governed IMPLEMENTING to TESTING to RELEASE_READY transitions."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from typing import cast

import pytest
from arch_runtime import ApplyTransitionCommand, ApplyTransitionResult, Runtime

from arch_web import (
    ApproveReleaseReadinessCommand,
    AuthorizeTestingCommand,
    EvidenceRef,
    ExecuteQAResult,
    PrepareQAResult,
    QAApprovalError,
    QAStatus,
    WebLifecycleStatus,
    approve_release_readiness,
    authorize_testing,
)
from w02.factories import REQUEST_ID
from w08.factories import qa_bundle
from w08.fakes import SequencedBrowser
from w08.test_aggregation import _execute


def _result(success: bool) -> ApplyTransitionResult:
    return cast(ApplyTransitionResult, SimpleNamespace(success=success))


class FakeRuntime:
    def __init__(self, success: bool = True, *, failure: Exception | None = None) -> None:
        self.result = _result(success)
        self.failure = failure
        self.commands: list[ApplyTransitionCommand] = []
        self.saved: dict[str, tuple[dict[str, object], ApplyTransitionResult]] = {}

    def apply_transition(self, command: ApplyTransitionCommand) -> ApplyTransitionResult:
        if self.failure is not None:
            raise self.failure
        payload = command.request_payload()
        previous = self.saved.get(command.idempotency_key)
        if previous is not None:
            if previous[0] != payload:
                raise RuntimeError("idempotency conflict")
            return previous[1]
        self.commands.append(command)
        self.saved[command.idempotency_key] = (payload, self.result)
        return self.result


def _authorize_command(prepared: PrepareQAResult, **changes: object) -> AuthorizeTestingCommand:
    candidate = prepared.candidate
    values: dict[str, object] = {
        "prepared": prepared,
        "project_status": WebLifecycleStatus.IMPLEMENTING,
        "approval_evidence": EvidenceRef(
            "approval:w08-testing", "human-qa-authorization", "urn:approval:w08-testing"
        ),
        "idempotency_key": "web:qa:authorize:1",
        "request_id": REQUEST_ID,
        "transition_key": "web.qa.testing",
        "expected_runtime_state": "implementing",
        "expected_record_version": candidate.runtime_record_version,
        "expected_record_fingerprint": candidate.runtime_record_fingerprint,
        "expected_content_fingerprint": "sha256:" + "d" * 64,
        "actor_id": "user:qa-reviewer",
        "actor_display_name": "QA Reviewer",
    }
    values.update(changes)
    return AuthorizeTestingCommand(**values)  # type: ignore[arg-type]


def _release_command(
    prepared: PrepareQAResult,
    executed: ExecuteQAResult,
    **changes: object,
) -> ApproveReleaseReadinessCommand:
    values: dict[str, object] = {
        "project_status": WebLifecycleStatus.TESTING,
        "prepared": prepared,
        "executed": executed,
        "approval_evidence": EvidenceRef(
            "approval:w08-release", "human-release-readiness", "urn:approval:w08-release"
        ),
        "idempotency_key": "web:qa:release-ready:1",
        "request_id": REQUEST_ID,
        "transition_key": "web.qa.release_ready",
        "expected_runtime_state": "testing",
        "expected_record_version": 9,
        "expected_record_fingerprint": "sha256:" + "e" * 64,
        "expected_content_fingerprint": "sha256:" + "f" * 64,
        "actor_id": "user:release-reviewer",
        "actor_display_name": "Release Reviewer",
    }
    values.update(changes)
    return ApproveReleaseReadinessCommand(**values)  # type: ignore[arg-type]


def test_testing_authorization_uses_public_runtime_and_exact_metadata(tmp_path: Path) -> None:
    _, prepared, _ = qa_bundle(tmp_path)
    runtime = FakeRuntime()
    result = authorize_testing(cast(Runtime, runtime), _authorize_command(prepared))
    assert result.authorization.authorized
    assert result.authorization.runtime_state is WebLifecycleStatus.TESTING
    metadata = runtime.commands[0].metadata
    assert metadata["web_transition"] == "IMPLEMENTING->TESTING"
    assert metadata["git_head"] == prepared.candidate.git_head
    assert metadata["qa_scope_fingerprint"] == prepared.scope.canonical_fingerprint()


def test_runtime_rejection_and_exact_retry_are_preserved(tmp_path: Path) -> None:
    _, prepared, _ = qa_bundle(tmp_path)
    rejected = authorize_testing(cast(Runtime, FakeRuntime(False)), _authorize_command(prepared))
    assert not rejected.authorization.authorized
    assert rejected.authorization.runtime_state is WebLifecycleStatus.IMPLEMENTING
    runtime = FakeRuntime()
    command = _authorize_command(prepared)
    assert authorize_testing(cast(Runtime, runtime), command) == authorize_testing(
        cast(Runtime, runtime), command
    )
    assert len(runtime.commands) == 1


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"project_status": WebLifecycleStatus.TESTING}, "IMPLEMENTING"),
        ({"expected_record_version": 99}, "stale"),
        ({"expected_record_fingerprint": "sha256:stale"}, "stale"),
    ],
)
def test_stale_testing_authorization_never_calls_runtime(
    tmp_path: Path, changes: dict[str, object], message: str
) -> None:
    _, prepared, _ = qa_bundle(tmp_path)
    runtime = FakeRuntime()
    with pytest.raises(QAApprovalError, match=message):
        authorize_testing(cast(Runtime, runtime), _authorize_command(prepared, **changes))
    assert not runtime.commands


def test_release_readiness_transition_binds_exact_qa_evidence(tmp_path: Path) -> None:
    _, prepared, profile = qa_bundle(tmp_path)
    executed = _execute(prepared, profile, SequencedBrowser((QAStatus.PASS,)))
    runtime = FakeRuntime()
    result = approve_release_readiness(cast(Runtime, runtime), _release_command(prepared, executed))
    assert result.runtime_result.success
    assert result.package.runtime_state is WebLifecycleStatus.TESTING
    metadata = runtime.commands[0].metadata
    assert metadata["web_transition"] == "TESTING->RELEASE_READY"
    assert metadata["blocking_finding_count"] == 0
    assert metadata["release_readiness_fingerprint"] == result.package.canonical_fingerprint()


@pytest.mark.parametrize(
    "mutation",
    [
        lambda prepared, executed: {"project_status": WebLifecycleStatus.IMPLEMENTING},
        lambda prepared, executed: {
            "executed": replace(
                executed,
                review=replace(
                    executed.review,
                    run_ref=replace(executed.review.run_ref, fingerprint="a" * 64),
                ),
            )
        },
        lambda prepared, executed: {
            "executed": replace(executed, preview=replace(executed.preview, cleanup_verified=False))
        },
    ],
)
def test_release_readiness_rejects_stale_or_blocked_evidence(
    tmp_path: Path,
    mutation: Callable[[PrepareQAResult, ExecuteQAResult], dict[str, object]],
) -> None:
    _, prepared, profile = qa_bundle(tmp_path)
    executed = _execute(prepared, profile, SequencedBrowser((QAStatus.PASS,)))
    changes = mutation(prepared, executed)
    changed_execution = cast(ExecuteQAResult, changes.pop("executed", executed))
    command = _release_command(prepared, changed_execution, **changes)
    with pytest.raises((QAApprovalError, ValueError)):
        approve_release_readiness(cast(Runtime, FakeRuntime()), command)


def test_infrastructure_failure_is_not_converted_to_domain_result(tmp_path: Path) -> None:
    _, prepared, _ = qa_bundle(tmp_path)
    with pytest.raises(OSError, match="database unavailable"):
        authorize_testing(
            cast(Runtime, FakeRuntime(failure=OSError("database unavailable"))),
            _authorize_command(prepared),
        )
