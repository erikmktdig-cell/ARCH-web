"""Exact disposable W09 reference fixture."""

from __future__ import annotations

import hashlib
from dataclasses import replace
from pathlib import Path

from arch_web import (
    DeploymentProviderProfile,
    DeploymentStrategy,
    EnvironmentClass,
    EnvironmentConfigContract,
    EvidenceRef,
    MigrationRisk,
    PrepareReleaseCommand,
    ProductionMigrationPlan,
    RecoveryDisposition,
    ReleaseArtifact,
    ReleaseReadinessPackage,
    ReleaseVersion,
    RollbackPlan,
    SecretReference,
    TargetEnvironment,
    WebLifecycleStatus,
    WebRoute,
)
from arch_web.contracts.versions import CURRENT_WEB_CONTRACT_VERSION
from arch_web.domain.workspace import ReconciliationStatus
from w02.factories import PROJECT_ID

SHA_A = "sha256:" + "a" * 64
SHA_B = "sha256:" + "b" * 64
SHA_C = "sha256:" + "c" * 64
GIT_HEAD = "f" * 40


def digest(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def artifact(tmp_path: Path) -> ReleaseArtifact:
    path = tmp_path / "release.html"
    path.write_text(
        '<!doctype html><main data-release-digest="bound" '
        'data-backend-health="pass" data-security-smoke="pass">Released</main>',
        encoding="utf-8",
    )
    return ReleaseArtifact(
        "artifact:web",
        "static_html",
        digest(path),
        str(path),
        True,
        lockfile_fingerprint=SHA_A,
        builder_identity="arch-web-test-builder@1",
        sbom_ref="urn:sbom:synthetic",
        signature_ref="urn:signature:synthetic",
    )


def readiness() -> ReleaseReadinessPackage:
    return ReleaseReadinessPackage(
        CURRENT_WEB_CONTRACT_VERSION,
        "RRP-w09",
        PROJECT_ID,
        WebLifecycleStatus.TESTING,
        SHA_A,
        SHA_B,
        GIT_HEAD,
        SHA_C,
        SHA_A,
        SHA_B,
        SHA_C,
        SHA_A,
        (SHA_B,),
        (),
        ReconciliationStatus.CLEAN,
        EvidenceRef(
            "approval:w08",
            "human-release-readiness",
            "urn:approval:w08",
            producer="arch-web-w08",
        ),
    )


def target(**changes: object) -> TargetEnvironment:
    values: dict[str, object] = {
        "environment_id": "production:reference",
        "environment_class": EnvironmentClass.PRODUCTION,
        "provider_profile_id": "provider:local-reference",
        "region": "loopback-disposable",
        "base_url_intent": "https://app.example.test",
        "datastore_target": "app-db:production-reference",
        "required_config_keys": ("APP_MODE",),
        "allowed_config_keys": ("APP_MODE", "PUBLIC_ORIGIN"),
        "required_secret_refs": ("DATABASE_URL",),
        "health_path": "/",
        "tls_required": False,
        "canonical_host": None,
    }
    values.update(changes)
    return TargetEnvironment(**values)  # type: ignore[arg-type]


def config(**changes: object) -> EnvironmentConfigContract:
    values: dict[str, object] = {
        "config_id": "config:production-reference",
        "environment_id": "production:reference",
        "values": (("APP_MODE", "production"),),
        "secret_refs": (SecretReference("DATABASE_URL", "provider://database-url"),),
        "derived_values": (),
    }
    values.update(changes)
    return EnvironmentConfigContract(**values)  # type: ignore[arg-type]


def provider(**changes: object) -> DeploymentProviderProfile:
    values: dict[str, object] = {
        "profile_id": "provider:local-reference",
        "adapter_identity": "arch-web.local-deployment@0.1.0",
        "capabilities": (
            "artifact_promotion",
            "direct_replace",
            "health_observation",
            "rollback",
        ),
        "supported_strategies": (DeploymentStrategy.STATIC_PUBLICATION,),
        "production_approved": True,
    }
    values.update(changes)
    return DeploymentProviderProfile(**values)  # type: ignore[arg-type]


def rollback(**changes: object) -> RollbackPlan:
    values: dict[str, object] = {
        "plan_id": "rollback:reference",
        "disposition": RecoveryDisposition.ROLLBACK,
        "prior_artifact_digest": SHA_B,
        "prior_deployment_ref": "deployment:previous",
        "migration_compatible": True,
        "verification_checks": ("health", "artifact"),
    }
    values.update(changes)
    return RollbackPlan(**values)  # type: ignore[arg-type]


def migration(**changes: object) -> ProductionMigrationPlan:
    statement = "CREATE TABLE release_evidence(id TEXT PRIMARY KEY)"
    checksum = "sha256:" + hashlib.sha256(statement.encode()).hexdigest()
    values: dict[str, object] = {
        "plan_id": "migration:reference",
        "target_datastore": "app-db:production-reference",
        "expected_schema_version": "1",
        "migration_ids": ("002-release-evidence",),
        "migration_checksums": (checksum,),
        "risk": MigrationRisk.COMPATIBLE,
        "backup_required": False,
        "authorized_irreversible": False,
        "rollback_compatible": True,
        "postcondition_schema_version": "2",
    }
    values.update(changes)
    return ProductionMigrationPlan(**values)  # type: ignore[arg-type]


def prepare_command(tmp_path: Path, *, with_migration: bool = False) -> PrepareReleaseCommand:
    ready = readiness()
    migration_plan = migration() if with_migration else None
    return PrepareReleaseCommand(
        PROJECT_ID,
        WebLifecycleStatus.RELEASE_READY,
        WebRoute.QUICK,
        10,
        SHA_A,
        ready,
        ReleaseVersion("0.1.0", GIT_HEAD, ready.source_tree_fingerprint),
        (artifact(tmp_path),),
        SHA_C,
        target(),
        config(),
        provider(),
        DeploymentStrategy.STATIC_PUBLICATION,
        migration_plan,
        rollback(),
        ("sbom", "signature"),
    )


def changed(command: PrepareReleaseCommand, **values: object) -> PrepareReleaseCommand:
    return replace(command, **values)  # type: ignore[arg-type]
