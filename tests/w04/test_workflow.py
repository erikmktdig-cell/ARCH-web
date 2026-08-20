"""W04 deterministic preparation, profiles, coverage, and findings."""

from __future__ import annotations

from dataclasses import replace

import pytest

from arch_web import (
    ArchitectureReviewPackage,
    ComponentStateName,
    DesignCoverageDisposition,
    DesignCoverageScope,
    DesignFindingCode,
    PrepareUISpecificationCommand,
    PrimitiveToken,
    PrimitiveTokenKind,
    SurfaceType,
    UIDesignPreparationError,
    UIReadiness,
    WebLifecycleStatus,
    WebRoute,
    analyze_ui_design,
    get_reference_profile,
    prepare_ui_specification,
    recommend_reference_profile,
    reference_design_profiles,
)
from arch_web.application.design.planning import plan_ui_contracts
from w04.factories import design_command, design_intent


@pytest.mark.parametrize("route", list(WebRoute))
def test_complete_explicit_inputs_are_ready_for_every_route(route: WebRoute) -> None:
    result = prepare_ui_specification(design_command(route))
    assert result.review_package.readiness is UIReadiness.READY_FOR_REVIEW
    assert result.review_package.findings == ()
    assert result.review_package.route is route


def test_equivalent_inputs_produce_identical_bytes() -> None:
    first = prepare_ui_specification(design_command(WebRoute.STANDARD))
    second = prepare_ui_specification(design_command(WebRoute.STANDARD))
    assert first.canonical_bytes() == second.canonical_bytes()
    assert first.canonical_fingerprint() == second.canonical_fingerprint()


def test_profile_recommendation_is_not_hidden_adoption() -> None:
    result = prepare_ui_specification(design_command(adopt_profile=False))
    assert result.review_package.selected_profile_ref is None
    assert result.profile_recommendation.requires_explicit_adoption
    assert result.review_package.readiness is UIReadiness.NOT_READY
    assert DesignFindingCode.PROFILE_NOT_EXPLICITLY_ADOPTED in {
        item.code for item in result.review_package.findings
    }


def test_profile_registry_is_small_versioned_and_canonical() -> None:
    profiles = reference_design_profiles()
    assert len(profiles) == 3
    assert len({item.profile_id for item in profiles}) == 3
    assert all(item.contract_version == "0.1.0" for item in profiles)
    assert get_reference_profile(profiles[0].profile_id) == profiles[0]
    with pytest.raises(KeyError):
        get_reference_profile("missing")


@pytest.mark.parametrize(
    ("surface_type", "expected"),
    [
        (SurfaceType.PAGE, "content_marketing_neutral"),
        (SurfaceType.DASHBOARD, "modern_product_neutral"),
        (SurfaceType.ADMIN, "dense_operational_neutral"),
    ],
)
def test_profile_recommendation_uses_architecture_not_taste(
    surface_type: SurfaceType, expected: str
) -> None:
    command = design_command(WebRoute.QUICK)
    surface = replace(command.architecture.surfaces[0], surface_type=surface_type)
    architecture = replace(
        command.architecture,
        surfaces=(surface,),
    )
    recommendation = recommend_reference_profile(architecture, command.route)
    assert recommendation.profile_id == expected


def test_explicit_accessibility_breaking_override_blocks_readiness() -> None:
    override = PrimitiveToken("color.action", PrimitiveTokenKind.COLOR, "#777777")
    result = prepare_ui_specification(design_command(overrides=(override,)))
    assert result.review_package.readiness is UIReadiness.NOT_READY
    assert DesignFindingCode.INSUFFICIENT_CONTRAST in {
        item.code for item in result.review_package.findings
    }


def test_surface_and_requirement_coverage_is_total() -> None:
    command = design_command(WebRoute.STANDARD)
    result = prepare_ui_specification(command)
    surface_items = {
        item.target_ref
        for item in result.coverage.items
        if item.scope is DesignCoverageScope.SURFACE
    }
    requirement_items = {
        item.target_ref
        for item in result.coverage.items
        if item.scope is DesignCoverageScope.REQUIREMENT
    }
    assert surface_items == {item.surface_id for item in command.architecture.surfaces}
    assert requirement_items == {item.requirement_id for item in command.requirements.requirements}
    assert all(
        item.disposition is not DesignCoverageDisposition.UNRESOLVED
        for item in result.coverage.items
    )
    assert any(
        item.disposition is DesignCoverageDisposition.DEFERRED_TO_IMPLEMENTATION
        for item in result.coverage.items
    )


def test_data_heavy_surface_gets_complete_states_and_responsive_fallback() -> None:
    result = prepare_ui_specification(design_command(WebRoute.STANDARD))
    data_components = [item for item in result.ui_specification.components if item.data_bearing]
    assert data_components
    for component in data_components:
        states = {item.state for item in component.states}
        assert {
            ComponentStateName.LOADING,
            ComponentStateName.EMPTY,
            ComponentStateName.ERROR,
        } <= states
    assert any(
        item.behavior.value == "table_fallback" for item in result.design_system.responsive.rules
    )


def test_every_surface_has_hierarchy_actions_accessibility_and_motion() -> None:
    result = prepare_ui_specification(design_command())
    for surface in result.ui_specification.surfaces:
        assert surface.content_hierarchy
        assert len(surface.primary_actions) == 1
        assert surface.responsive_rule_refs
        assert surface.accessibility_requirements
        assert surface.motion_refs


def test_semantic_mutation_changes_design_and_ui_fingerprints() -> None:
    result = prepare_ui_specification(design_command())
    changed_intent = replace(result.design_intent, visual_personality="precise and technical")
    assert changed_intent.canonical_fingerprint() != result.design_intent.canonical_fingerprint()
    changed_surface = replace(result.ui_specification.surfaces[0], primary_task="Changed task")
    changed_ui = replace(result.ui_specification, surfaces=(changed_surface,))
    assert changed_ui.canonical_fingerprint() != result.ui_specification.canonical_fingerprint()


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("project_status", WebLifecycleStatus.REQUIREMENTS_APPROVED, "ARCHITECTURE_APPROVED"),
        ("project_id", "different", "identity"),
        ("expected_requirements_fingerprint", "0" * 64, "Requirements"),
        ("expected_architecture_fingerprint", "0" * 64, "Architecture fingerprint"),
        ("expected_architecture_review_fingerprint", "0" * 64, "review fingerprint"),
        ("route", WebRoute.CRITICAL, "route mismatch"),
    ],
)
def test_upstream_bindings_fail_closed(field: str, value: object, message: str) -> None:
    command = design_command()
    changed = replace(command, **{field: value})  # type: ignore[arg-type]
    with pytest.raises(UIDesignPreparationError, match=message):
        prepare_ui_specification(changed)


def test_design_intent_project_and_unresolved_items_are_governed() -> None:
    command = design_command(design_intent=design_intent(project_id="different"))
    with pytest.raises(UIDesignPreparationError, match="identity"):
        prepare_ui_specification(command)
    result = prepare_ui_specification(
        design_command(design_intent=design_intent(unresolved_items=("brand approval",)))
    )
    assert result.review_package.readiness is UIReadiness.NOT_READY
    assert DesignFindingCode.MISSING_DESIGN_INTENT in {
        item.code for item in result.review_package.findings
    }


def test_prepare_has_no_runtime_dependency_or_mutation_argument() -> None:
    command = design_command()
    assert "runtime" not in PrepareUISpecificationCommand.__dataclass_fields__
    prepare_ui_specification(command)


def test_missing_component_states_and_raw_tokens_are_blocking_findings() -> None:
    command = design_command()
    result = prepare_ui_specification(command)
    component = next(
        item for item in result.ui_specification.components if item.interaction.primary_action
    )
    changed_component = replace(
        component,
        states=tuple(
            item for item in component.states if item.state is not ComponentStateName.FOCUS_VISIBLE
        ),
        semantic_token_refs=("#FFFFFF",),
    )
    changed_ui = replace(
        result.ui_specification,
        components=tuple(
            changed_component if item.component_id == component.component_id else item
            for item in result.ui_specification.components
        ),
    )
    findings = analyze_ui_design(command, result.design_system, changed_ui, result.coverage)
    codes = {item.code for item in findings}
    assert DesignFindingCode.MISSING_COMPONENT_STATE in codes
    assert DesignFindingCode.RAW_TOKEN_BYPASS in codes


def test_modal_planning_and_missing_focus_management_are_enforced() -> None:
    command = design_command()
    architecture_surface = replace(
        command.architecture.surfaces[0], surface_type=SurfaceType.MODAL_FLOW
    )
    architecture = replace(command.architecture, surfaces=(architecture_surface,))
    _, planned_ui = plan_ui_contracts(
        command.design_intent,
        command.requirements,
        architecture,
        command.selected_profile,
        command.primitive_overrides,
        command.design_evidence,
    )
    dialog = next(item for item in planned_ui.components if item.semantic_role == "content-region")
    assert dialog.interaction.pattern_role == "dialog"
    assert dialog.accessibility.focus_management_intent is not None

    result = prepare_ui_specification(command)
    findings = analyze_ui_design(
        replace(command, architecture=architecture),
        result.design_system,
        result.ui_specification,
        result.coverage,
    )
    assert DesignFindingCode.MISSING_MODAL_FOCUS_MANAGEMENT in {item.code for item in findings}


def test_form_semantics_and_primary_action_provenance_are_enforced() -> None:
    command = design_command()
    result = prepare_ui_specification(command)
    content = next(
        item for item in result.ui_specification.components if not item.interaction.primary_action
    )
    action = next(
        item for item in result.ui_specification.components if item.interaction.primary_action
    )
    invalid_form = replace(
        content,
        form_control=True,
        accessibility=replace(
            content.accessibility,
            label_intent="placeholder only",
            error_identification="none",
        ),
    )
    unauthorized_action = replace(action, requirement_refs=())
    changed_ui = replace(
        result.ui_specification,
        components=(invalid_form, unauthorized_action),
    )
    findings = analyze_ui_design(command, result.design_system, changed_ui, result.coverage)
    codes = {item.code for item in findings}
    assert DesignFindingCode.MISSING_FORM_SEMANTICS in codes
    assert DesignFindingCode.UNAUTHORIZED_UI_BEHAVIOR in codes


def test_architecture_review_type_remains_exact() -> None:
    command = design_command()
    assert isinstance(command.architecture_review, ArchitectureReviewPackage)
