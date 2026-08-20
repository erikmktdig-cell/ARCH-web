"""W03 immutable contracts and codec regression tests."""

from __future__ import annotations

from dataclasses import FrozenInstanceError, replace

import pytest

from arch_web import (
    ArchitectureFinding,
    ArchitectureFindingCode,
    ArchitectureFindingSeverity,
    ArchitectureReadiness,
    CoverageDisposition,
    NavigationEdge,
    NavigationKind,
    NavigationModel,
    NavigationNode,
    NavigationRelationship,
    NavigationVisibility,
    RequirementCoverage,
    UserJourney,
    WebContractValidationError,
    decode_contract,
    encode_contract,
    prepare_architecture,
)
from w03.factories import architecture_command


@pytest.mark.parametrize(
    "field",
    ["information_architecture", "navigation_model", "review_package"],
)
def test_major_w03_records_round_trip_canonical_json(field: str) -> None:
    value = getattr(prepare_architecture(architecture_command()), field)
    assert decode_contract(type(value), encode_contract(value)) == value


def test_navigation_nested_records_round_trip() -> None:
    navigation = prepare_architecture(architecture_command()).navigation_model
    for value in (*navigation.nodes, *navigation.edges, *navigation.journeys):
        assert decode_contract(type(value), encode_contract(value)) == value


def test_review_nested_records_round_trip() -> None:
    review = prepare_architecture(architecture_command()).review_package
    for value in (*review.coverage, *review.findings):
        assert decode_contract(type(value), encode_contract(value)) == value


def test_navigation_records_are_deeply_tuple_backed_and_frozen() -> None:
    navigation = prepare_architecture(architecture_command()).navigation_model
    assert isinstance(navigation.nodes, tuple)
    with pytest.raises(FrozenInstanceError):
        navigation.project_id = "changed"  # type: ignore[misc]


def test_navigation_node_edge_and_journey_validation_branches() -> None:
    with pytest.raises(WebContractValidationError, match="non-negative"):
        NavigationNode(
            "node",
            "surface",
            "Label",
            NavigationKind.PRIMARY,
            NavigationVisibility.PUBLIC,
            ("user",),
            -1,
        )
    with pytest.raises(WebContractValidationError, match="parent itself"):
        NavigationNode(
            "node",
            "surface",
            "Label",
            NavigationKind.PRIMARY,
            NavigationVisibility.PUBLIC,
            ("user",),
            0,
            parent_node_ref="node",
        )
    with pytest.raises(WebContractValidationError, match="point to itself"):
        NavigationEdge("edge", "node", "node", NavigationRelationship.JOURNEY)
    with pytest.raises(WebContractValidationError, match="at least one"):
        UserJourney("journey", "Name", "actor", (), "outcome")


def test_navigation_rejects_duplicate_nodes_and_missing_edge_refs() -> None:
    node = NavigationNode(
        "node",
        "surface",
        "Label",
        NavigationKind.PRIMARY,
        NavigationVisibility.PUBLIC,
        ("user",),
        0,
    )
    with pytest.raises(WebContractValidationError, match="duplicate"):
        NavigationModel("nav", "project", (node, node))
    edge = NavigationEdge("edge", "node", "missing", NavigationRelationship.CONTEXTUAL)
    with pytest.raises(WebContractValidationError, match="edge reference"):
        NavigationModel("nav", "project", (node,), (edge,))


def test_coverage_requires_target_only_for_deferral() -> None:
    with pytest.raises(ValueError, match="target"):
        RequirementCoverage("requirement", CoverageDisposition.DEFERRED_TO_W04, "reason")
    with pytest.raises(ValueError, match="target"):
        RequirementCoverage("requirement", CoverageDisposition.COVERED, "reason", "W04")


def test_blocking_finding_cannot_claim_readiness() -> None:
    result = prepare_architecture(architecture_command())
    review = result.review_package
    blocker = ArchitectureFinding(
        "finding",
        ArchitectureFindingCode.UNCOVERED_REQUIREMENT,
        ArchitectureFindingSeverity.BLOCKING,
        "Blocked",
    )
    with pytest.raises(ValueError, match="NOT_READY"):
        replace(review, findings=(blocker,), readiness=ArchitectureReadiness.READY_FOR_REVIEW)
    with pytest.raises(ValueError, match="approval evidence"):
        replace(review, readiness=ArchitectureReadiness.APPROVED)


def test_semantic_mutation_changes_architecture_fingerprint() -> None:
    architecture = prepare_architecture(architecture_command()).information_architecture
    surface = replace(architecture.surfaces[0], name="Changed meaning")
    changed = replace(architecture, surfaces=(surface,))
    assert changed.canonical_fingerprint() != architecture.canonical_fingerprint()


def test_review_constructor_sorts_findings_and_coverage() -> None:
    review = prepare_architecture(architecture_command()).review_package
    coverage = RequirementCoverage(
        "z", CoverageDisposition.COVERED, "reason", architecture_refs=("x",)
    )
    coverage2 = RequirementCoverage(
        "a", CoverageDisposition.COVERED, "reason", architecture_refs=("x",)
    )
    warning = ArchitectureFinding(
        "z",
        ArchitectureFindingCode.MISSING_PROVENANCE,
        ArchitectureFindingSeverity.WARNING,
        "warning",
    )
    warning2 = replace(warning, finding_id="a")
    changed = replace(review, coverage=(coverage, coverage2), findings=(warning, warning2))
    assert [item.requirement_ref for item in changed.coverage] == ["a", "z"]
    assert [item.finding_id for item in changed.findings] == ["a", "z"]
