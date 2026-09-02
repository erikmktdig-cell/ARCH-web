"""Final public Runtime authority after verified external deployment."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from typing import cast

import pytest
from arch_runtime import ApplyTransitionCommand, ApplyTransitionResult, Runtime

from arch_web import (
    ApproveDeploymentCommand,
    AuthorizeDeploymentCommand,
    DeploymentApprovalError,
    DeploymentOutcome,
    EvidenceRef,
    ExecuteDeploymentCommand,
    LocalDeploymentProvider,
    VerifyDeploymentCommand,
    WebLifecycleStatus,
    approve_deployment,
    authorize_deployment,
    execute_deployment,
    prepare_release,
    verify_deployment,
)
from arch_web.domain.workspace import ReconciliationStatus
from runtime_authority import runtime_project
from w02.factories import PROJECT_ID, REQUEST_ID
from w09.factories import SHA_A, prepare_command, provider, target


class FakeRuntime:
    def __init__(self, success: bool = True, failure: Exception | None = None) -> None:
        self.result = cast(ApplyTransitionResult, SimpleNamespace(success=success))
        self.failure = failure
        self.commands: list[ApplyTransitionCommand] = []
        self.saved: dict[str, tuple[dict[str, object], ApplyTransitionResult]] = {}
        self.project = runtime_project(
            WebLifecycleStatus.RELEASE_READY,
            project_id=PROJECT_ID,
            record_version=10,
            record_fingerprint=SHA_A,
            content_fingerprint="sha256:" + "d" * 64,
        )

    def get_project(self, project_id: object) -> object:
        return self.project

    def apply_transition(self, command: ApplyTransitionCommand) -> ApplyTransitionResult:
        if self.failure is not None:
            raise self.failure
        payload = command.request_payload()
        prior = self.saved.get(command.idempotency_key)
        if prior is not None:
            if prior[0] != payload:
                raise RuntimeError("idempotency conflict")
            return prior[1]
        self.commands.append(command)
        self.saved[command.idempotency_key] = (payload, self.result)
        return self.result


def _deployed(tmp_path: Path) -> tuple[object, ...]:
    source = prepare_command(tmp_path)
    prepared = prepare_release(source)
    approval = EvidenceRef(
        "approval:execute", "human-deployment-authorization", "urn:approval:execute"
    )
    authorization = authorize_deployment(
        AuthorizeDeploymentCommand(
            prepared,
            target(),
            provider(),
            None,
            "deploy:runtime",
            "deployment:previous",
            (approval,),
        )
    ).authorization
    adapter = LocalDeploymentProvider(tmp_path / "deployments")
    receipt = execute_deployment(
        ExecuteDeploymentCommand(
            prepared, authorization, source.artifacts[0], source.target, source.config, None
        ),
        adapter,
    ).receipt
    verification = verify_deployment(
        VerifyDeploymentCommand(prepared, receipt, source.target), adapter
    )
    return source, prepared, authorization, adapter, receipt, verification


def _command(bundle: tuple[object, ...], **changes: object) -> ApproveDeploymentCommand:
    source, prepared, authorization, _, receipt, verification = bundle
    values: dict[str, object] = {
        "project_status": WebLifecycleStatus.RELEASE_READY,
        "prepared": prepared,
        "authorization": authorization,
        "receipt": receipt,
        "verification": verification,
        "target": source.target,  # type: ignore[attr-defined]
        "approval_evidence": (
            EvidenceRef("approval:final", "human-final-deployment", "urn:approval:final"),
        ),
        "idempotency_key": "web:deployment:approve:1",
        "request_id": REQUEST_ID,
        "transition_key": "web.release.deployed",
        "expected_runtime_state": "RELEASE_READY",
        "expected_record_version": 10,
        "expected_record_fingerprint": SHA_A,
        "expected_content_fingerprint": "sha256:" + "d" * 64,
        "actor_id": "user:release-reviewer",
        "actor_display_name": "Release Reviewer",
    }
    values.update(changes)
    return ApproveDeploymentCommand(**values)  # type: ignore[arg-type]


def test_runtime_transition_occurs_only_after_exact_verification(tmp_path: Path) -> None:
    bundle = _deployed(tmp_path)
    adapter = bundle[3]
    runtime = FakeRuntime()
    try:
        result = approve_deployment(cast(Runtime, runtime), _command(bundle))
        assert result.runtime_result.success
        assert result.package.approved
        metadata = runtime.commands[0].metadata
        assert metadata["web_transition"] == "RELEASE_READY->DEPLOYED"
        assert metadata["blocking_finding_count"] == "0"
        assert metadata["artifact_digest"] == bundle[0].artifacts[0].digest  # type: ignore[attr-defined]
    finally:
        adapter.close()  # type: ignore[attr-defined]


def test_exact_final_retry_calls_runtime_once_and_never_redeploys(tmp_path: Path) -> None:
    bundle = _deployed(tmp_path)
    adapter = bundle[3]
    runtime = FakeRuntime()
    command = _command(bundle)
    try:
        assert approve_deployment(cast(Runtime, runtime), command) == approve_deployment(
            cast(Runtime, runtime), command
        )
        assert len(runtime.commands) == 1
        assert len(tuple((tmp_path / "deployments").iterdir())) == 1
    finally:
        adapter.close()  # type: ignore[attr-defined]


@pytest.mark.parametrize(
    "mutation",
    [
        lambda bundle: {"project_status": WebLifecycleStatus.TESTING},
        lambda bundle: {"approval_evidence": ()},
        lambda bundle: {"expected_record_version": 99},
        lambda bundle: {"expected_record_fingerprint": "sha256:" + "9" * 64},
        lambda bundle: {"authorization": replace(bundle[2], authorized=False)},
        lambda bundle: {"receipt": replace(bundle[4], candidate_fingerprint="sha256:" + "9" * 64)},
        lambda bundle: {"receipt": replace(bundle[4], plan_fingerprint="sha256:" + "9" * 64)},
        lambda bundle: {"receipt": replace(bundle[4], artifact_digest="sha256:" + "9" * 64)},
        lambda bundle: {
            "receipt": replace(
                bundle[4],
                reconciliation_status=ReconciliationStatus.REQUIRED,
                outcome=DeploymentOutcome.RECONCILIATION_REQUIRED,
            )
        },
        lambda bundle: {
            "verification": replace(
                bundle[5], evidence=replace(bundle[5].evidence, passed=False, health_passed=False)
            )
        },
        lambda bundle: {"target": replace(bundle[0].target, region="changed")},
    ],
)
def test_no_invalid_or_stale_evidence_can_mark_deployed(
    tmp_path: Path, mutation: Callable[[tuple[object, ...]], dict[str, object]]
) -> None:
    bundle = _deployed(tmp_path)
    runtime = FakeRuntime()
    try:
        with pytest.raises((DeploymentApprovalError, ValueError)):
            approve_deployment(cast(Runtime, runtime), _command(bundle, **mutation(bundle)))
        assert not runtime.commands
    finally:
        bundle[3].close()  # type: ignore[attr-defined]


def test_runtime_rejection_or_infrastructure_failure_preserves_external_evidence(
    tmp_path: Path,
) -> None:
    bundle = _deployed(tmp_path)
    adapter = bundle[3]
    try:
        rejected = approve_deployment(cast(Runtime, FakeRuntime(False)), _command(bundle))
        assert not rejected.runtime_result.success
        assert bundle[4].endpoint is not None  # type: ignore[attr-defined]
        with pytest.raises(OSError, match="runtime unavailable"):
            approve_deployment(
                cast(Runtime, FakeRuntime(failure=OSError("runtime unavailable"))), _command(bundle)
            )
        assert bundle[4].reconciliation_status is ReconciliationStatus.CLEAN  # type: ignore[attr-defined]
    finally:
        adapter.close()  # type: ignore[attr-defined]
