"""W09 deterministic candidate, planning, authorization, and policy tests."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from arch_web import (
    AuthorizeDeploymentCommand,
    DeploymentAuthorizationError,
    DeploymentStrategy,
    EnvironmentConfigContract,
    EvidenceRef,
    MigrationRisk,
    RecoveryDisposition,
    ReleasePreparationError,
    ReleaseReadiness,
    SecretReference,
    WebLifecycleStatus,
    WebRoute,
    authorize_deployment,
    prepare_release,
)
from w09.factories import changed, config, migration, prepare_command, provider, rollback, target


def reviews(count: int = 1) -> tuple[EvidenceRef, ...]:
    return tuple(
        EvidenceRef(
            f"approval:execute:{index}",
            "human-deployment-authorization",
            f"urn:approval:execute:{index}",
        )
        for index in range(count)
    )


def authorization_command(prepared: object, **changes: object) -> AuthorizeDeploymentCommand:
    values: dict[str, object] = {
        "prepared": prepared,
        "target": target(),
        "provider": provider(),
        "migration_plan": None,
        "execution_id": "deploy:reference:1",
        "expected_prior_deployment_ref": "deployment:previous",
        "reviewer_evidence": reviews(),
    }
    values.update(changes)
    return AuthorizeDeploymentCommand(**values)  # type: ignore[arg-type]


def test_prepare_is_deterministic_and_has_no_external_mutation(tmp_path: Path) -> None:
    command = prepare_command(tmp_path)
    first = prepare_release(command)
    second = prepare_release(command)
    assert first == second
    assert first.review.readiness is ReleaseReadiness.READY_FOR_EXECUTION
    assert tuple(step.order for step in first.plan.steps) == tuple(range(1, 14))
    assert [step.action for step in first.plan.steps if step.mutating] == ["deploy_artifact"]


@pytest.mark.parametrize(
    ("change", "message"),
    [
        ({"project_status": WebLifecycleStatus.TESTING}, "RELEASE_READY"),
        ({"project_id": "PRJ-01HZX7M3FQ1T2Q9V8Y6K4C2B1C"}, "project mismatch"),
        ({"target": target(provider_profile_id="wrong")}, "provider profile"),
        ({"strategy": DeploymentStrategy.CANARY}, "unsupported"),
        ({"provider": provider(production_approved=False)}, "approved for production"),
    ],
)
def test_prepare_rejects_wrong_authoritative_inputs(
    tmp_path: Path, change: dict[str, object], message: str
) -> None:
    with pytest.raises(ReleasePreparationError, match=message):
        prepare_release(changed(prepare_command(tmp_path), **change))


def test_stale_git_or_tree_never_becomes_candidate(tmp_path: Path) -> None:
    command = prepare_command(tmp_path)
    assert command.release_version is not None
    for version in (
        replace(command.release_version, source_commit="e" * 40),
        replace(command.release_version, source_tree_fingerprint="sha256:" + "e" * 64),
    ):
        with pytest.raises(ReleasePreparationError, match="stale"):
            prepare_release(changed(command, release_version=version))


@pytest.mark.parametrize(
    "bad_config",
    [
        config(environment_id="staging:wrong"),
        config(values=()),
        config(values=(("APP_MODE", "production"), ("UNKNOWN", "value"))),
        config(secret_refs=()),
        config(values=(("APP_MODE", "http://localhost:3000"),)),
        config(values=(("APP_MODE", "mock-service"),)),
        config(values=(("APP_MODE", "changeme"),)),
        config(values=(("APP_MODE", "token=synthetic-secret"),)),
    ],
)
def test_invalid_production_config_is_blocking(
    tmp_path: Path, bad_config: EnvironmentConfigContract
) -> None:
    result = prepare_release(changed(prepare_command(tmp_path), config=bad_config))
    assert result.review.readiness is ReleaseReadiness.BLOCKED
    assert any(item.blocking for item in result.review.findings)


def test_secret_reference_rejects_value_material() -> None:
    with pytest.raises(ValueError, match="reference"):
        SecretReference("API_TOKEN", "token=not-a-reference")


@pytest.mark.parametrize(
    "migration_plan",
    [
        migration(target_datastore="wrong-db"),
        migration(risk=MigrationRisk.DESTRUCTIVE, backup_required=False),
        migration(risk=MigrationRisk.IRREVERSIBLE, authorized_irreversible=False),
    ],
)
def test_unsafe_migration_governance_blocks(tmp_path: Path, migration_plan: object) -> None:
    result = prepare_release(changed(prepare_command(tmp_path), migration_plan=migration_plan))
    assert result.review.readiness is ReleaseReadiness.BLOCKED


def test_irreversible_migration_cannot_claim_rollback(tmp_path: Path) -> None:
    plan = migration(
        risk=MigrationRisk.IRREVERSIBLE,
        authorized_irreversible=True,
        rollback_compatible=False,
    )
    result = prepare_release(changed(prepare_command(tmp_path), migration_plan=plan))
    assert {item.code for item in result.review.findings} == {"invalid_rollback_claim"}
    assert rollback(disposition=RecoveryDisposition.ROLL_FORWARD_ONLY, migration_compatible=False)


def test_required_provenance_and_unknown_policy_block(tmp_path: Path) -> None:
    command = prepare_command(tmp_path)
    artifact = replace(command.artifacts[0], sbom_ref=None, signature_ref=None)
    result = prepare_release(
        changed(command, artifacts=(artifact,), required_provenance=("sbom", "signature", "slsa"))
    )
    assert result.review.readiness is ReleaseReadiness.BLOCKED
    assert {item.code for item in result.review.findings} == {
        "required_provenance_missing",
        "unsupported_provenance",
    }


def test_critical_route_requires_guarded_strategy_and_two_reviewers(tmp_path: Path) -> None:
    command = changed(
        prepare_command(tmp_path),
        route=WebRoute.CRITICAL,
        strategy=DeploymentStrategy.DIRECT_REPLACE,
        provider=provider(supported_strategies=(DeploymentStrategy.DIRECT_REPLACE,)),
    )
    with pytest.raises(ReleasePreparationError, match="Critical"):
        prepare_release(command)
    prepared = prepare_release(
        changed(
            command,
            strategy=DeploymentStrategy.CANARY,
            provider=provider(supported_strategies=(DeploymentStrategy.CANARY,)),
        )
    )
    critical_provider = provider(supported_strategies=(DeploymentStrategy.CANARY,))
    with pytest.raises(DeploymentAuthorizationError, match="Route-specific"):
        authorize_deployment(authorization_command(prepared, provider=critical_provider))
    result = authorize_deployment(
        authorization_command(prepared, provider=critical_provider, reviewer_evidence=reviews(2))
    )
    assert result.authorization.authorized


def test_authorization_binds_plan_target_provider_migration_and_reviews(tmp_path: Path) -> None:
    prepared = prepare_release(prepare_command(tmp_path))
    result = authorize_deployment(authorization_command(prepared))
    assert result.authorization.plan_fingerprint == prepared.plan.canonical_fingerprint()
    mutations = (
        {"target": target(region="changed")},
        {"provider": provider(adapter_identity="changed@1")},
        {"migration_plan": migration()},
        {"reviewer_evidence": ()},
    )
    for mutation in mutations:
        with pytest.raises(DeploymentAuthorizationError):
            authorize_deployment(authorization_command(prepared, **mutation))


def test_blocked_review_cannot_be_authorized(tmp_path: Path) -> None:
    prepared = prepare_release(changed(prepare_command(tmp_path), config=config(values=())))
    with pytest.raises(DeploymentAuthorizationError, match="Blocking"):
        authorize_deployment(authorization_command(prepared))
