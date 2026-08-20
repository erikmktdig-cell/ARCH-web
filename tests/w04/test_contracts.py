"""W04 immutability, state completeness, references, and codec tests."""

from __future__ import annotations

from dataclasses import FrozenInstanceError, replace

import pytest

from arch_web import (
    AccessibilitySpec,
    ComponentStateName,
    ComponentStateSpec,
    DesignCoverageDisposition,
    DesignCoverageItem,
    DesignCoverageScope,
    DesignFinding,
    DesignFindingCode,
    DesignFindingSeverity,
    UIReadiness,
    WebContractReferenceError,
    WebContractValidationError,
    decode_contract,
    encode_contract,
    prepare_ui_specification,
)
from w04.factories import design_command


@pytest.mark.parametrize(
    "field",
    ["design_intent", "design_system", "ui_specification", "coverage", "review_package"],
)
def test_top_level_w04_contracts_round_trip_canonical_json(field: str) -> None:
    value = getattr(prepare_ui_specification(design_command()), field)
    assert decode_contract(type(value), encode_contract(value)) == value


def test_profile_recommendation_and_profile_round_trip() -> None:
    command = design_command()
    result = prepare_ui_specification(command)
    values = (result.profile_recommendation, command.selected_profile)
    for value in values:
        assert value is not None
        assert decode_contract(type(value), encode_contract(value)) == value


def test_nested_design_records_round_trip() -> None:
    result = prepare_ui_specification(design_command())
    design = result.design_system
    values = (
        *design.primitive_tokens.tokens,
        design.primitive_tokens,
        *design.semantic_tokens.tokens,
        design.semantic_tokens,
        *design.contrast_pairs,
        *design.typography.roles,
        design.typography,
        design.layout,
        *design.responsive.breakpoints,
        *design.responsive.rules,
        design.responsive,
        *design.motion.motions,
        design.motion,
    )
    for value in values:
        assert decode_contract(type(value), encode_contract(value)) == value


def test_nested_ui_and_review_records_round_trip() -> None:
    result = prepare_ui_specification(design_command())
    values = (
        *result.ui_specification.components,
        *result.ui_specification.surfaces,
        *result.coverage.items,
        *result.review_package.findings,
    )
    for value in values:
        assert decode_contract(type(value), encode_contract(value)) == value


def test_records_are_frozen_and_collections_are_tuples() -> None:
    result = prepare_ui_specification(design_command())
    assert isinstance(result.ui_specification.components, tuple)
    assert isinstance(result.design_system.semantic_tokens.tokens, tuple)
    with pytest.raises(FrozenInstanceError):
        result.design_intent.visual_personality = "changed"  # type: ignore[misc]


def test_accessibility_target_and_optional_focus_management_validation() -> None:
    accessibility = AccessibilitySpec("name", "label", True, True, True, "text errors", 44)
    assert accessibility.focus_management_intent is None
    with pytest.raises(WebContractValidationError, match="24"):
        replace(accessibility, target_size_minimum=20)
    with pytest.raises(WebContractValidationError, match="focus_management"):
        replace(accessibility, focus_management_intent=" ")


def test_coverage_deferral_and_uniqueness_invariants() -> None:
    with pytest.raises(ValueError, match="target phase"):
        DesignCoverageItem(
            DesignCoverageScope.REQUIREMENT,
            "requirement",
            DesignCoverageDisposition.DEFERRED_TO_IMPLEMENTATION,
            "later",
        )
    with pytest.raises(ValueError, match="target phase"):
        DesignCoverageItem(
            DesignCoverageScope.REQUIREMENT,
            "requirement",
            DesignCoverageDisposition.SPECIFIED,
            "now",
            target_phase="W06",
        )
    result = prepare_ui_specification(design_command()).coverage
    with pytest.raises(ValueError, match="unique"):
        replace(result, items=(result.items[0], result.items[0]))


def test_blocking_finding_cannot_claim_review_readiness() -> None:
    result = prepare_ui_specification(design_command())
    finding = DesignFinding(
        "finding",
        DesignFindingCode.UNRESOLVED_UI_REQUIREMENT,
        DesignFindingSeverity.BLOCKING,
        "blocked",
    )
    with pytest.raises(ValueError, match="NOT_READY"):
        replace(
            result.review_package,
            findings=(finding,),
            readiness=UIReadiness.READY_FOR_REVIEW,
        )
    with pytest.raises(ValueError, match="approval evidence"):
        replace(result.review_package, readiness=UIReadiness.APPROVED)


def test_component_state_ordering_and_duplicates() -> None:
    component = prepare_ui_specification(design_command()).ui_specification.components[0]
    states = (
        ComponentStateSpec(ComponentStateName.ERROR, "error"),
        ComponentStateSpec(ComponentStateName.DEFAULT, "default"),
    )
    changed = replace(component, states=states)
    assert [item.state for item in changed.states] == [
        ComponentStateName.DEFAULT,
        ComponentStateName.ERROR,
    ]
    with pytest.raises(WebContractValidationError, match="states"):
        replace(component, states=(states[0], states[0]))


def test_ui_cross_references_fail_closed() -> None:
    result = prepare_ui_specification(design_command())
    component = replace(result.ui_specification.components[0], surface_refs=("missing",))
    with pytest.raises(WebContractReferenceError, match="surface"):
        replace(result.ui_specification, components=(component,))
    surface = replace(result.ui_specification.surfaces[0], component_refs=("missing",))
    with pytest.raises(WebContractReferenceError, match="component"):
        replace(result.ui_specification, surfaces=(surface,))
