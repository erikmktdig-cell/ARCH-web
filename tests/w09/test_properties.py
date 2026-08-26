"""Generative W09 determinism and fail-closed properties."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from arch_web import (
    DeploymentApprovalPackage,
    EnvironmentConfigContract,
    ReleaseFinding,
    ReleaseFindingSeverity,
    ReleaseReadiness,
    ReleaseReviewPackage,
    SecretReference,
    WebLifecycleStatus,
    prepare_release,
)
from arch_web.domain.workspace import ReconciliationStatus
from w09.factories import SHA_A, changed, config, prepare_command


@given(
    st.dictionaries(
        st.sampled_from(("APP_MODE", "PUBLIC_ORIGIN")),
        st.text(min_size=1, max_size=20).filter(lambda value: value.strip() == value),
        min_size=1,
    )
)
def test_config_canonicalization_is_order_invariant(values: dict[str, str]) -> None:
    refs = (SecretReference("DATABASE_URL", "provider://database-url"),)
    first = EnvironmentConfigContract("config", "env", tuple(values.items()), refs)
    second = EnvironmentConfigContract(
        "config", "env", tuple(reversed(tuple(values.items()))), refs
    )
    assert first.canonical_bytes() == second.canonical_bytes()


@given(st.lists(st.sampled_from(("a", "b", "c", "d")), unique=True))
def test_finding_order_is_canonical(codes: list[str]) -> None:
    findings = tuple(
        ReleaseFinding(
            f"finding:{code}", code, ReleaseFindingSeverity.ADVISORY, False, f"Finding {code}"
        )
        for code in codes
    )
    forward = ReleaseReviewPackage(
        "review", SHA_A, SHA_A, findings, ReleaseReadiness.READY_FOR_EXECUTION
    )
    reverse = ReleaseReviewPackage(
        "review", SHA_A, SHA_A, tuple(reversed(findings)), ReleaseReadiness.READY_FOR_EXECUTION
    )
    assert forward.canonical_bytes() == reverse.canonical_bytes()


@given(
    st.text(min_size=1, max_size=30).filter(
        lambda value: value.strip() == value and value not in {"HEAD", "main", "latest"}
    )
)
@settings(suppress_health_check=(HealthCheck.function_scoped_fixture,))
def test_semantic_release_version_mutation_changes_candidate_fingerprint(
    tmp_path: Path, version: str
) -> None:
    command = prepare_command(tmp_path)
    assert command.release_version is not None
    base = prepare_release(command).candidate
    changed_version = replace(command.release_version, version=version)
    candidate = prepare_release(changed(command, release_version=changed_version)).candidate
    assert (candidate.canonical_fingerprint() == base.canonical_fingerprint()) == (
        version == "0.1.0"
    )


@given(st.sampled_from(("localhost", "127.0.0.1", "mock-api", "test.db", "changeme", "token=raw")))
@settings(suppress_health_check=(HealthCheck.function_scoped_fixture,))
def test_production_leakage_never_becomes_deployable(tmp_path: Path, unsafe: str) -> None:
    result = prepare_release(
        changed(prepare_command(tmp_path), config=config(values=(("APP_MODE", unsafe),)))
    )
    assert result.review.readiness is ReleaseReadiness.BLOCKED
    assert any(item.blocking for item in result.review.findings)


def test_blocker_or_reconciliation_can_never_form_approved_package() -> None:
    finding = ReleaseFinding("block", "blocked", ReleaseFindingSeverity.BLOCKER, True, "Blocked")
    values = {
        "contract_version": "0.1.0",
        "package_id": "package",
        "project_id": "project",
        "route": "quick",
        "runtime_state": WebLifecycleStatus.RELEASE_READY,
        "runtime_record_version": 1,
        "runtime_record_fingerprint": SHA_A,
        "release_readiness_fingerprint": SHA_A,
        "candidate_fingerprint": SHA_A,
        "environment_fingerprint": SHA_A,
        "plan_fingerprint": SHA_A,
        "authorization_fingerprint": SHA_A,
        "receipt_fingerprint": SHA_A,
        "verification_fingerprint": SHA_A,
        "rollback_plan_fingerprint": SHA_A,
        "findings": (finding,),
        "reconciliation_status": ReconciliationStatus.REQUIRED,
        "reviewer_evidence": (),
        "approved": True,
    }
    with pytest.raises((TypeError, ValueError)):
        DeploymentApprovalPackage(**values)  # type: ignore[arg-type]
