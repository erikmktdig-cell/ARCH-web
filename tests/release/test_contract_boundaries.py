"""Release regression checks for existing approval and contract boundaries."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import fields, is_dataclass, replace
from typing import Any

import pytest

from arch_web import QAStatus, RequirementsReadiness, WebLifecycleStatus
from w02.test_approval_bridge import approval_command as requirements_command
from w03.test_approval import approval_command as architecture_command
from w04.test_approval import approval_command as design_command
from w05.test_runtime import approval_command as workspace_command
from w06.test_authorization import authorization_command as frontend_command
from w07.factories import backend_bundle
from w08.factories import qa_bundle
from w08.fakes import SequencedBrowser
from w08.test_aggregation import _execute
from w08.test_runtime_bridge import _authorize_command, _release_command
from w09.test_runtime_bridge import _command, _deployed

pytestmark = pytest.mark.release


@pytest.fixture(scope="module")
def boundary_evidence(tmp_path_factory: pytest.TempPathFactory) -> Iterator[dict[str, Any]]:
    """Use approved workflow fixtures, with disposable execution and provider cleanup."""
    root = tmp_path_factory.mktemp("release-boundaries")
    for name in ("workspace", "frontend", "backend", "qa"):
        (root / name).mkdir()
    commands = {
        "requirements": requirements_command(),
        "architecture": architecture_command(),
        "design": design_command(),
        "workspace": workspace_command(root / "workspace"),
        "frontend": frontend_command(root / "frontend"),
    }
    backend = backend_bundle(root / "backend")
    _, prepared, profile = qa_bundle(root / "qa")
    executed = _execute(prepared, profile, SequencedBrowser((QAStatus.PASS,)))
    commands["testing"] = _authorize_command(prepared)
    commands["readiness"] = _release_command(prepared, executed)
    deployment_root = root / "deployment"
    deployment_root.mkdir()
    deployment = _deployed(deployment_root)
    commands["deployment"] = _command(deployment)
    try:
        yield {
            "commands": commands,
            "backend": backend,
            "deployment": deployment,
            "profile": profile,
        }
    finally:
        adapter: Any = deployment[3]
        adapter.close()


@pytest.mark.parametrize(
    "workflow",
    [
        "requirements",
        "architecture",
        "design",
        "workspace",
        "frontend",
        "testing",
        "readiness",
        "deployment",
    ],
)
@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"expected_record_version": 0}, "positive"),
        ({"expected_workflow_record_version": 1}, "together"),
        ({"expected_workflow_content_fingerprint": "sha256:" + "a" * 64}, "together"),
        (
            {
                "expected_workflow_record_version": 0,
                "expected_workflow_content_fingerprint": "sha256:" + "a" * 64,
            },
            "positive",
        ),
        (
            {"expected_workflow_record_version": 1, "expected_workflow_content_fingerprint": ""},
            "empty",
        ),
    ],
)
def test_approval_rejects_incomplete_or_invalid_optimistic_preconditions(
    boundary_evidence: dict[str, Any],
    workflow: str,
    changes: dict[str, Any],
    message: str,
) -> None:
    command = boundary_evidence["commands"][workflow]
    with pytest.raises(ValueError, match=message):
        replace(command, **changes)


@pytest.mark.parametrize(
    "workflow",
    [
        "requirements",
        "architecture",
        "design",
        "workspace",
        "frontend",
        "testing",
        "readiness",
        "deployment",
    ],
)
def test_explicit_workflow_preconditions_and_anonymous_display_are_preserved(
    boundary_evidence: dict[str, Any],
    workflow: str,
) -> None:
    command = replace(
        boundary_evidence["commands"][workflow],
        actor_display_name=None,
        expected_workflow_record_version=1,
        expected_workflow_content_fingerprint="sha256:" + "a" * 64,
    )
    assert command.expected_workflow_record_version == 1
    assert command.expected_workflow_content_fingerprint == "sha256:" + "a" * 64
    assert command.actor_display_name is None


def _domain_records(value: Any) -> Iterator[Any]:
    if is_dataclass(value) and not isinstance(value, type):
        if type(value).__module__.startswith("arch_web.domain."):
            yield value
        for field in fields(value):
            yield from _domain_records(getattr(value, field.name))
    elif isinstance(value, (tuple, list)):
        for item in value:
            yield from _domain_records(item)
    elif isinstance(value, dict):
        for item in value.values():
            yield from _domain_records(item)


def test_workflow_domain_records_round_trip_individually(
    boundary_evidence: dict[str, Any],
) -> None:
    seen: set[tuple[type[Any], bytes]] = set()
    for record in _domain_records(boundary_evidence):
        raw = record.canonical_bytes()
        key = (type(record), raw)
        if key in seen:
            continue
        seen.add(key)
        restored = type(record).from_data(record.canonical_data())
        assert restored == record, type(record).__name__
        assert restored.canonical_bytes() == raw
        assert restored.canonical_fingerprint() == record.canonical_fingerprint()
    assert len({kind for kind, _ in seen}) >= 100


def _record(evidence: dict[str, Any], name: str) -> Any:
    return next(item for item in _domain_records(evidence) if type(item).__name__ == name)


@pytest.mark.parametrize("field", ["product_brief_ref", "requirements_contract_ref"])
def test_review_references_cannot_change_contract_type(
    boundary_evidence: dict[str, Any],
    field: str,
) -> None:
    review = _record(boundary_evidence, "RequirementsReviewPackage")
    wrong = replace(getattr(review, field), target_contract_type="unrelated_contract")
    with pytest.raises(ValueError, match="wrong contract type"):
        replace(review, **{field: wrong})


def test_review_cannot_self_approve(boundary_evidence: dict[str, Any]) -> None:
    with pytest.raises(ValueError, match="runtime acceptance"):
        replace(
            _record(boundary_evidence, "RequirementsReviewPackage"),
            readiness=RequirementsReadiness.APPROVED,
        )


@pytest.mark.parametrize(
    ("name", "changes", "message"),
    [
        ("DataEntitySpec", {"identity_field_ref": "missing"}, "identity field"),
        ("FailurePolicy", {"expose_internal_detail": True}, "internal detail"),
        ("BackendOperationContract", {"authorization_rule_ref": None}, "authorization"),
        ("BackendOperationContract", {"idempotency_required": True}, "Idempotency"),
        ("BackendArtifact", {"content": ""}, "empty"),
        ("BackendAssignmentPacket", {"runtime_state": WebLifecycleStatus.DRAFT}, "IMPLEMENTING"),
        ("BackendAssignmentPacket", {"runtime_record_version": 0}, "positive"),
        (
            "FrontendAssignmentPacket",
            {"runtime_state": WebLifecycleStatus.DRAFT},
            "IMPLEMENTATION_READY",
        ),
        ("FrontendAssignmentPacket", {"runtime_record_version": 0}, "positive"),
        ("FrontendAssignmentPacket", {"selected_unit_refs": ()}, "unit"),
        ("FrontendArtifact", {"content": ""}, "empty"),
        ("FileEvidence", {"size": -1}, "negative"),
        ("ImplementationUnit", {"acceptance_evidence": ()}, "acceptance"),
        (
            "WorkspaceExecutionPolicy",
            {"create_local_commit": True, "commit_message": None},
            "message",
        ),
        (
            "BrowserSupportPolicy",
            {"engines": ("chromium", "chromium"), "browser_versions": ("1", "2")},
            "unique",
        ),
        ("ViewportPolicy", {"breakpoint_boundaries": (100,)}, "small"),
        ("QABaselineProfile", {"performance_budgets": (("load", 1.0), ("load", 2.0))}, "unique"),
        ("QABaselineProfile", {"visual_threshold": 2.0}, "between"),
        ("QAStep", {"expectations": ()}, "expectation"),
        ("ReleaseCandidateManifest", {"runtime_state": WebLifecycleStatus.DRAFT}, "RELEASE_READY"),
        ("ReleaseCandidateManifest", {"runtime_record_version": 0}, "positive"),
        ("ReleaseCandidateManifest", {"artifacts": ()}, "tested"),
        ("ReleaseCandidateManifest", {"project_id": "other-project"}, "project mismatch"),
        ("ReleaseVersion", {"source_commit": "HEAD"}, "pinned"),
        ("ReleaseVersion", {"source_commit": "main"}, "pinned"),
        ("ReleaseVersion", {"source_commit": "latest"}, "pinned"),
        ("RollbackPlan", {"migration_compatible": False}, "incompatible"),
        ("DesignProfileRecommendation", {"requires_explicit_adoption": False}, "adoption"),
        ("RouteRecommendation", {"requires_human_confirmation": False}, "confirmation"),
    ],
)
def test_invalid_domain_evidence_fails_closed(
    boundary_evidence: dict[str, Any],
    name: str,
    changes: dict[str, Any],
    message: str,
) -> None:
    original = _record(boundary_evidence, name)
    fingerprint = original.canonical_fingerprint()
    with pytest.raises(ValueError, match=message):
        replace(original, **changes)
    assert original.canonical_fingerprint() == fingerprint


@pytest.mark.parametrize(
    ("name", "field"),
    [
        ("DataEntitySpec", "fields"),
        ("WorkspaceBaseline", "toolchain_capabilities"),
        ("ImplementationPlan", "units"),
        ("WorkspaceChangeSet", "changes"),
        ("QAStep", "expectations"),
        ("ReleaseCandidateManifest", "artifacts"),
        ("RequirementsReviewPackage", "source_evidence_refs"),
    ],
)
def test_duplicate_record_identities_are_rejected(
    boundary_evidence: dict[str, Any],
    name: str,
    field: str,
) -> None:
    record = _record(boundary_evidence, name)
    values = getattr(record, field)
    if name == "RequirementsReviewPackage":
        values = (_record(boundary_evidence, "EvidenceRef"),)
    assert values
    with pytest.raises(ValueError, match=r"unique|duplicate"):
        replace(record, **{field: (*values, values[0])})


@pytest.mark.parametrize(
    ("name", "changes"),
    [
        ("DataLifecyclePolicy", {"anonymization_policy": "erase identifying fields"}),
        (
            "BackendOperationContract",
            {"authentication_required": False, "authorization_rule_ref": None},
        ),
        ("AuthorizationRule", {"ownership_condition": None}),
        ("PersistenceContract", {"configuration_secret_ref": None}),
        ("ApplicationMigrationPlan", {"steps": ()}),
        ("BackendAssignmentPacket", {"git_head": "f" * 40}),
        ("FrontendAssignmentPacket", {"git_head": "f" * 40}),
        ("FrontendDataBinding", {"boundary_name": None}),
        ("QAStep", {"value": "user input"}),
        ("ReleaseCandidateManifest", {"release_version": None}),
        ("RollbackPlan", {"prior_artifact_digest": None, "prior_deployment_ref": None}),
    ],
)
def test_optional_evidence_variants_round_trip_without_inventing_values(
    boundary_evidence: dict[str, Any],
    name: str,
    changes: dict[str, Any],
) -> None:
    record = replace(_record(boundary_evidence, name), **changes)
    restored = type(record).from_data(record.canonical_data())
    assert restored == record
    for field, expected in changes.items():
        assert getattr(restored, field) == expected


def test_nested_release_and_plan_evidence_must_match(boundary_evidence: dict[str, Any]) -> None:
    candidate = _record(boundary_evidence, "ReleaseCandidateManifest")
    for changes, message in (
        ({"release_version": replace(candidate.release_version, source_commit="e" * 40)}, "commit"),
        (
            {
                "release_version": replace(
                    candidate.release_version, source_tree_fingerprint="stale"
                )
            },
            "tree",
        ),
        ({"artifacts": (replace(candidate.artifacts[0], tested=False),)}, "tested"),
    ):
        with pytest.raises(ValueError, match=message):
            replace(candidate, **changes)
    plan = _record(boundary_evidence, "DeploymentPlan")
    with pytest.raises(ValueError, match="contiguous"):
        replace(plan, steps=(replace(plan.steps[0], order=2),))
    implementation = _record(boundary_evidence, "ImplementationPlan")
    with pytest.raises(ValueError, match="dependency"):
        replace(
            implementation, units=(replace(implementation.units[0], dependency_refs=("missing",)),)
        )
    with pytest.raises(ValueError, match="missing unit"):
        replace(
            implementation,
            path_claims=(replace(implementation.path_claims[0], unit_ref="missing"),),
        )
    migrations = _record(boundary_evidence, "ApplicationMigrationPlan")
    with pytest.raises(ValueError, match="predecessor"):
        replace(
            migrations,
            steps=(
                *migrations.steps,
                replace(
                    migrations.steps[0],
                    migration_id="second",
                    predecessor="missing",
                ),
            ),
        )
