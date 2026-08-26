"""Disposable provider, migration, rollback, and reconciliation integration."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from arch_web import (
    AuthorizeDeploymentCommand,
    DeploymentExecutionAuthorization,
    DeploymentExecutionError,
    DeploymentOutcome,
    DeploymentReceipt,
    DeploymentVerificationError,
    EvidenceRef,
    ExecuteDeploymentCommand,
    LocalDeploymentProvider,
    PrepareReleaseCommand,
    PrepareReleaseResult,
    ProductionMigrationPlan,
    VerifyDeploymentCommand,
    authorize_deployment,
    execute_deployment,
    prepare_release,
    verify_deployment,
)
from arch_web.domain.workspace import ReconciliationStatus
from w09.factories import (
    artifact,
    changed,
    config,
    prepare_command,
    provider,
    target,
)


def _authorization(
    prepared: PrepareReleaseResult,
    *,
    migration_plan: ProductionMigrationPlan | None = None,
    execution_id: str = "deploy:integration",
) -> DeploymentExecutionAuthorization:
    return authorize_deployment(
        AuthorizeDeploymentCommand(
            prepared,
            target(),
            provider(),
            migration_plan,
            execution_id,
            "deployment:previous",
            (
                EvidenceRef(
                    "approval:execute", "human-deployment-authorization", "urn:approval:execute"
                ),
            ),
        )
    ).authorization


def _execute(
    tmp_path: Path, *, with_migration: bool = False
) -> tuple[
    PrepareReleaseCommand,
    PrepareReleaseResult,
    DeploymentExecutionAuthorization,
    LocalDeploymentProvider,
    DeploymentReceipt,
    Path,
]:
    command = prepare_command(tmp_path, with_migration=with_migration)
    prepared = prepare_release(command)
    authorization = _authorization(prepared, migration_plan=command.migration_plan)
    state_path = tmp_path / "application-schema.version"
    state_path.write_text("1", encoding="utf-8")
    provider_adapter = LocalDeploymentProvider(tmp_path / "deployments", state_path)
    result = execute_deployment(
        ExecuteDeploymentCommand(
            prepared,
            authorization,
            command.artifacts[0],
            command.target,
            command.config,
            command.migration_plan,
        ),
        provider_adapter,
    )
    return command, prepared, authorization, provider_adapter, result.receipt, state_path


def test_reference_vertical_slice_serves_exact_artifact_and_real_http(tmp_path: Path) -> None:
    command, prepared, _, provider_adapter, receipt, _ = _execute(tmp_path)
    try:
        assert receipt.outcome is DeploymentOutcome.APPLIED_PENDING_VERIFICATION
        assert receipt.observed_artifact_digest == command.artifacts[0].digest
        verified = verify_deployment(
            VerifyDeploymentCommand(prepared, receipt, command.target), provider_adapter
        )
        assert verified.evidence.passed
        assert dict(verified.evidence.check_results) == {
            "artifact": "pass",
            "backend": "pass",
            "health": "pass",
            "mock_leakage": "pass",
            "security": "pass",
            "smoke": "pass",
            "tls": "pass",
        }
    finally:
        provider_adapter.close()


def test_exact_retry_is_no_second_external_mutation(tmp_path: Path) -> None:
    command, prepared, authorization, provider_adapter, first, _ = _execute(tmp_path)
    try:
        second = execute_deployment(
            ExecuteDeploymentCommand(
                prepared,
                authorization,
                command.artifacts[0],
                command.target,
                command.config,
                None,
            ),
            provider_adapter,
        ).receipt
        assert second == first
        assert len(tuple((tmp_path / "deployments").iterdir())) == 1
    finally:
        provider_adapter.close()


def test_same_execution_id_different_authority_conflicts(tmp_path: Path) -> None:
    command, prepared, authorization, provider_adapter, _, _ = _execute(tmp_path)
    try:
        with pytest.raises(DeploymentExecutionError, match="conflict"):
            provider_adapter.deploy(
                replace(authorization, plan_fingerprint="sha256:" + "9" * 64),
                prepared.plan,
                command.artifacts[0],
                command.target,
                None,
            )
    finally:
        provider_adapter.close()


def test_artifact_digest_mismatch_never_deploys(tmp_path: Path) -> None:
    command = prepare_command(tmp_path)
    prepared = prepare_release(command)
    authorization = _authorization(prepared)
    Path(command.artifacts[0].uri).write_text("mutated", encoding="utf-8")
    with (
        LocalDeploymentProvider(tmp_path / "deployments") as adapter,
        pytest.raises(DeploymentExecutionError, match="digest"),
    ):
        execute_deployment(
            ExecuteDeploymentCommand(
                prepared,
                authorization,
                command.artifacts[0],
                command.target,
                command.config,
                None,
            ),
            adapter,
        )
    assert not any((tmp_path / "deployments").iterdir())


def test_authorized_inputs_cannot_drift_before_execution(tmp_path: Path) -> None:
    command = prepare_command(tmp_path)
    prepared = prepare_release(command)
    authorization = _authorization(prepared)
    mutations = (
        {"artifact": replace(command.artifacts[0], digest="sha256:" + "9" * 64)},
        {"target": target(region="changed")},
        {"config": config(values=(("APP_MODE", "changed"),))},
    )
    with LocalDeploymentProvider(tmp_path / "deployments") as adapter:
        for values in mutations:
            args = {
                "prepared": prepared,
                "authorization": authorization,
                "artifact": command.artifacts[0],
                "target": command.target,
                "config": command.config,
                "migration_plan": None,
            }
            args.update(values)
            with pytest.raises(DeploymentExecutionError, match="changed"):
                execute_deployment(ExecuteDeploymentCommand(**args), adapter)  # type: ignore[arg-type]


def test_provider_adapter_identity_cannot_drift(tmp_path: Path) -> None:
    class WrongAdapter(LocalDeploymentProvider):
        identity = "different-provider@1"

    command = prepare_command(tmp_path)
    prepared = prepare_release(command)
    authorization = _authorization(prepared)
    with (
        WrongAdapter(tmp_path / "deployments") as adapter,
        pytest.raises(DeploymentExecutionError, match="identity"),
    ):
        execute_deployment(
            ExecuteDeploymentCommand(
                prepared,
                authorization,
                command.artifacts[0],
                command.target,
                command.config,
                None,
            ),
            adapter,
        )


def test_disposable_application_migration_checks_exact_schema(tmp_path: Path) -> None:
    command, prepared, _, adapter, receipt, state_path = _execute(tmp_path, with_migration=True)
    try:
        assert state_path.read_text(encoding="utf-8") == "2"
        assert receipt.migration_evidence is not None
        assert command.migration_plan is not None
        assert (
            receipt.migration_evidence.applied_migration_ids == command.migration_plan.migration_ids
        )
        assert verify_deployment(
            VerifyDeploymentCommand(prepared, receipt, command.target), adapter
        )
    finally:
        adapter.close()


def test_wrong_application_schema_blocks_before_deploy(tmp_path: Path) -> None:
    command = prepare_command(tmp_path, with_migration=True)
    prepared = prepare_release(command)
    authorization = _authorization(prepared, migration_plan=command.migration_plan)
    state_path = tmp_path / "application-schema.version"
    state_path.write_text("unexpected", encoding="utf-8")
    with (
        LocalDeploymentProvider(tmp_path / "deployments", state_path) as adapter,
        pytest.raises(DeploymentExecutionError, match="precondition"),
    ):
        execute_deployment(
            ExecuteDeploymentCommand(
                prepared,
                authorization,
                command.artifacts[0],
                command.target,
                command.config,
                command.migration_plan,
            ),
            adapter,
        )


@pytest.mark.parametrize(
    "receipt_change",
    [
        {
            "reconciliation_status": ReconciliationStatus.REQUIRED,
            "outcome": DeploymentOutcome.RECONCILIATION_REQUIRED,
        },
        {"endpoint": None},
        {"observed_artifact_digest": None},
        {"artifact_digest": "sha256:" + "9" * 64},
        {"candidate_fingerprint": "sha256:" + "9" * 64},
        {"outcome": DeploymentOutcome.FAILED_NO_EXTERNAL_CHANGE},
        {"outcome": DeploymentOutcome.FAILED_ROLLED_BACK_VERIFIED},
    ],
)
def test_unverifiable_receipt_never_advances(
    tmp_path: Path, receipt_change: dict[str, object]
) -> None:
    command, prepared, _, adapter, receipt, _ = _execute(tmp_path)
    try:
        with pytest.raises(DeploymentVerificationError):
            verify_deployment(
                VerifyDeploymentCommand(
                    prepared,
                    replace(receipt, **receipt_change),  # type: ignore[arg-type]
                    command.target,
                ),
                adapter,
            )
    finally:
        adapter.close()


def test_health_or_application_smoke_failure_blocks(tmp_path: Path) -> None:
    command = prepare_command(tmp_path)
    bad_path = Path(command.artifacts[0].uri)
    bad_path.write_text(
        '<!doctype html><main data-release-digest="bound">bad</main>', encoding="utf-8"
    )
    bad_artifact = artifact(tmp_path)
    Path(bad_artifact.uri).write_text(
        '<!doctype html><main data-release-digest="bound">bad</main>', encoding="utf-8"
    )
    bad_artifact = replace(
        bad_artifact,
        digest="sha256:"
        + __import__("hashlib").sha256(Path(bad_artifact.uri).read_bytes()).hexdigest(),
    )
    prepared = prepare_release(changed(command, artifacts=(bad_artifact,)))
    authorization = _authorization(prepared)
    with LocalDeploymentProvider(tmp_path / "deployments") as adapter:
        receipt = execute_deployment(
            ExecuteDeploymentCommand(
                prepared, authorization, bad_artifact, command.target, command.config, None
            ),
            adapter,
        ).receipt
        with pytest.raises(DeploymentVerificationError, match="failed"):
            verify_deployment(VerifyDeploymentCommand(prepared, receipt, command.target), adapter)


def test_rollback_stops_exact_deployment_and_is_verified(tmp_path: Path) -> None:
    _, prepared, _, adapter, receipt, _ = _execute(tmp_path)
    evidence = adapter.rollback(prepared.plan.rollback_plan, receipt)
    assert evidence.success
    assert evidence.verified
    second = adapter.rollback(prepared.plan.rollback_plan, receipt)
    assert not second.success
    assert not second.verified
    adapter.close()
