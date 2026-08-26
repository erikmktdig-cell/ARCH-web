"""W09 immutable contract and codec coverage."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import FrozenInstanceError, replace
from pathlib import Path

import pytest

from arch_web import (
    DeploymentAttempt,
    DeploymentOutcome,
    DeploymentProviderProfile,
    DeploymentReceipt,
    DeploymentStep,
    EnvironmentClass,
    EnvironmentConfigContract,
    PostDeployVerificationEvidence,
    ProductionMigrationExecutionEvidence,
    ReleaseFinding,
    ReleaseFindingSeverity,
    ReleaseReadiness,
    ReleaseReviewPackage,
    RollbackExecutionEvidence,
    SecretReference,
    TargetEnvironment,
    decode_contract,
    encode_contract,
    prepare_release,
)
from arch_web.domain.workspace import ReconciliationStatus
from w09.factories import SHA_A, SHA_B, prepare_command, provider, target


def test_candidate_and_plan_round_trip_canonical_json(tmp_path: Path) -> None:
    prepared = prepare_release(prepare_command(tmp_path))
    for value in (prepared.candidate, prepared.plan, prepared.review, prepared.plan.rollback_plan):
        assert decode_contract(type(value), encode_contract(value)) == value
        assert (
            value.canonical_fingerprint()
            == decode_contract(type(value), encode_contract(value)).canonical_fingerprint()
        )


def test_contracts_are_frozen_and_normalize_semantic_collections(tmp_path: Path) -> None:
    prepared = prepare_release(prepare_command(tmp_path))
    with pytest.raises(FrozenInstanceError):
        prepared.plan.plan_id = "changed"  # type: ignore[misc]
    profile = provider(capabilities=("rollback", "artifact_promotion"))
    assert profile.capabilities == ("artifact_promotion", "rollback")
    config = EnvironmentConfigContract(
        "config:ordered",
        "production:reference",
        (("Z", "2"), ("A", "1")),
        (SecretReference("Z_SECRET", "provider://z"), SecretReference("A_SECRET", "provider://a")),
    )
    assert config.values == (("A", "1"), ("Z", "2"))
    assert tuple(item.name for item in config.secret_refs) == ("A_SECRET", "Z_SECRET")


@pytest.mark.parametrize(
    "factory",
    [
        lambda: DeploymentStep("step", 0, "action", False),
        lambda: DeploymentProviderProfile("provider", "adapter", (), (), True),
        lambda: TargetEnvironment(
            "env",
            EnvironmentClass.PRODUCTION,
            "provider",
            "region",
            "url",
            None,
            (),
            (),
            (),
            "health",
            False,
        ),
        lambda: SecretReference("secret", "password=raw"),
    ],
)
def test_contract_invariants_fail_closed(factory: Callable[[], object]) -> None:
    with pytest.raises(ValueError, match=r"must|requires|reference"):
        factory()


def test_execution_evidence_round_trips() -> None:
    migration = ProductionMigrationExecutionEvidence(
        SHA_A, "app-db", "1", "2", ("m1",), True, SHA_B
    )
    receipt = DeploymentReceipt(
        "execution",
        SHA_A,
        SHA_B,
        "provider",
        "environment",
        SHA_A,
        "provider-deployment",
        None,
        "http://127.0.0.1/",
        SHA_A,
        DeploymentOutcome.APPLIED_PENDING_VERIFICATION,
        ReconciliationStatus.CLEAN,
        "adapter@1",
        (SHA_B,),
        migration,
    )
    verification = PostDeployVerificationEvidence(
        "verification",
        SHA_A,
        receipt.canonical_fingerprint(),
        SHA_A,
        (("health", "pass"),),
        True,
        True,
        True,
        True,
        True,
        True,
        False,
        True,
    )
    for value in (migration, receipt, verification):
        assert decode_contract(type(value), encode_contract(value)) == value


def test_attempt_findings_review_and_rollback_evidence_are_exact() -> None:
    attempt = DeploymentAttempt("execution", SHA_A, SHA_B, "provider", None)
    finding = ReleaseFinding(
        "finding",
        "advisory",
        ReleaseFindingSeverity.ADVISORY,
        False,
        "Optional provenance unavailable",
    )
    review = ReleaseReviewPackage(
        "review", SHA_A, SHA_B, (finding,), ReleaseReadiness.READY_FOR_EXECUTION
    )
    rollback = RollbackExecutionEvidence(SHA_A, "provider-deployment", True, True, SHA_B)
    for value in (attempt, finding, review, rollback):
        assert decode_contract(type(value), encode_contract(value)) == value
    with pytest.raises(ValueError, match="contradicts"):
        replace(review, readiness=ReleaseReadiness.BLOCKED)
    with pytest.raises(ValueError, match="verified"):
        replace(rollback, success=False)


def test_digest_and_verification_summary_validation() -> None:
    with pytest.raises(ValueError, match="SHA-256"):
        DeploymentAttempt("execution", "bad", SHA_B, "provider", None).canonical_bytes()
    with pytest.raises(ValueError, match="contradicts"):
        PostDeployVerificationEvidence(
            "verification",
            SHA_A,
            SHA_B,
            SHA_A,
            (),
            True,
            True,
            True,
            True,
            True,
            True,
            False,
            False,
        )


def test_environment_requires_absolute_health_path() -> None:
    with pytest.raises(ValueError, match="absolute"):
        target(health_path="health")
