"""Rare but public release evidence remains validated and serializable."""

from dataclasses import replace
from datetime import datetime
from typing import Any

import pytest

from arch_web import (
    DeploymentAttempt,
    ExternalIntegrationContract,
    PostDeployVerificationPlan,
    ProductionMigrationExecutionEvidence,
    ReleaseFinding,
    ReleaseFindingSeverity,
    RollbackExecutionEvidence,
    reference_design_profiles,
)
from arch_web.contracts.canonical import canonical_bytes
from w09.factories import SHA_A, migration

pytestmark = pytest.mark.release


@pytest.mark.parametrize(
    "record",
    [
        ExternalIntegrationContract(
            "integration",
            "provider",
            "outbound",
            "fetch approved data",
            "provider://key",
            10,
            "none",
            True,
            False,
            "redact",
            "metadata only",
        ),
        ProductionMigrationExecutionEvidence(SHA_A, "app-db", "1", "2", ("002",), True, SHA_A),
        RollbackExecutionEvidence(SHA_A, "deployment:1", True, True, SHA_A),
        DeploymentAttempt("execution:1", SHA_A, SHA_A, "provider:1", None),
        PostDeployVerificationPlan("verify:1", SHA_A, SHA_A, SHA_A, "/health", ("health",)),
        ReleaseFinding(
            "finding:1",
            "missing-evidence",
            ReleaseFindingSeverity.BLOCKER,
            True,
            "Evidence unavailable",
        ),
    ],
)
def test_optional_records_have_exact_public_round_trip(record: Any) -> None:
    restored = type(record).from_data(record.canonical_data())
    assert restored == record
    assert restored.canonical_bytes() == record.canonical_bytes()


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"timeout_seconds": 0}, "positive"),
        ({"direction": "inbound_webhook", "webhook_signature_required": False}, "signature"),
    ],
)
def test_integration_requires_timeout_and_webhook_authenticity(
    changes: dict[str, Any],
    message: str,
) -> None:
    integration = ExternalIntegrationContract(
        "integration",
        "provider",
        "outbound",
        "fetch",
        None,
        10,
        "none",
        True,
        False,
        "redact",
        "metadata only",
    )
    with pytest.raises(ValueError, match=message):
        replace(integration, **changes)


def test_migration_ids_and_checksums_must_align() -> None:
    with pytest.raises(ValueError, match="align"):
        migration(migration_checksums=())


def test_blocker_cannot_be_marked_nonblocking() -> None:
    with pytest.raises(ValueError, match="must block"):
        ReleaseFinding("f", "missing", ReleaseFindingSeverity.BLOCKER, False, "Missing evidence")


@pytest.mark.parametrize("field", ["primitive_tokens", "semantic_tokens"])
def test_design_profiles_reject_duplicate_roles(field: str) -> None:
    profile = reference_design_profiles()[0]
    values = getattr(profile, field)
    changes: dict[str, Any] = {field: (*values, values[0])}
    with pytest.raises(ValueError, match="duplicate roles"):
        replace(profile, **changes)


def test_design_profile_requires_supported_route() -> None:
    with pytest.raises(ValueError, match="at least one route"):
        replace(reference_design_profiles()[0], supported_routes=())


@pytest.mark.parametrize("value", [datetime(2026, 1, 1), {1: "ambiguous-key"}, object()])
def test_canonical_json_rejects_ambiguous_or_unsupported_values(value: object) -> None:
    with pytest.raises(ValueError, match=r"naive|keys must be strings|Unsupported canonical"):
        canonical_bytes(value)
