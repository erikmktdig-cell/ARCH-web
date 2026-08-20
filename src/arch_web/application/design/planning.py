"""Deterministic design-system, component, and surface planning."""

from __future__ import annotations

from arch_web.application.architecture.planning import semantic_id
from arch_web.application.design.tokens import build_token_sets
from arch_web.contracts.versions import CURRENT_WEB_CONTRACT_VERSION
from arch_web.domain._base import WebContractRecord
from arch_web.domain.design_intent import DesignIntent, ReferenceDesignProfile
from arch_web.domain.design_tokens import ContrastPairSpec, PrimitiveToken
from arch_web.domain.enums import SurfaceType
from arch_web.domain.information_architecture import WebInformationArchitectureContract
from arch_web.domain.references import ContractRef, DesignReference
from arch_web.domain.requirements import WebRequirementsContract
from arch_web.domain.ui_specification import (
    AccessibilitySpec,
    BreakpointSpec,
    ComponentStateName,
    ComponentStateSpec,
    ComponentVariantSpec,
    InteractionSpec,
    LayoutSystem,
    MotionPolicy,
    MotionPurpose,
    MotionSpec,
    ResponsiveBehavior,
    ResponsivePolicy,
    ResponsiveRule,
    SurfaceUISpec,
    TypographyRole,
    TypographySystem,
    UIComponentSpec,
    WebDesignSystemContract,
    WebUISpecificationContract,
)


def _ref(target: WebContractRecord, contract_id: str) -> ContractRef:
    return ContractRef(
        target_contract_type=target.contract_type,
        contract_id=contract_id,
        contract_version=getattr(target, "contract_version", CURRENT_WEB_CONTRACT_VERSION),
        fingerprint=target.canonical_fingerprint(),
    )


def _foundations(
    architecture: WebInformationArchitectureContract,
    profile: ReferenceDesignProfile | None,
    overrides: tuple[PrimitiveToken, ...],
) -> tuple[
    WebDesignSystemContract,
    tuple[ResponsiveRule, ...],
]:
    primitives, semantics = build_token_sets(profile, overrides)
    typography = TypographySystem(
        typography_id=semantic_id("TYP", profile.profile_id if profile else "unresolved"),
        roles=(
            TypographyRole(
                "heading",
                "font.family.body",
                "font.size.heading",
                "font.weight.strong",
                1.2,
                1,
            ),
            TypographyRole(
                "body",
                "font.family.body",
                "font.size.body",
                "font.weight.regular",
                1.5,
                2,
            ),
        ),
        paragraph_measure="45-75 characters",
        numeric_treatment=(
            "tabular"
            if any(s.surface_type is SurfaceType.DASHBOARD for s in architecture.surfaces)
            else "proportional"
        ),
    )
    density = profile.density if profile is not None else "unresolved"
    layout = LayoutSystem(
        layout_id=semantic_id("LAY", {"density": density, "project": architecture.project_id}),
        container_strategy="fluid with constrained readable content",
        content_max_width_token_ref="layout.content.max",
        gutter_token_ref="space.4",
        stack_gap_token_refs=("space.2", "space.4", "space.6"),
        radius_token_refs=("radius.control",),
        elevation_token_refs=("elevation.raised",),
        density=density,
    )
    breakpoints = (
        BreakpointSpec("narrow", 0, 599),
        BreakpointSpec("regular", 600, 1199),
        BreakpointSpec("wide", 1200),
    )
    surface_refs = tuple(item.surface_id for item in architecture.surfaces)
    rules: tuple[ResponsiveRule, ...] = (
        ResponsiveRule(
            "responsive.narrow.reflow",
            "narrow",
            ResponsiveBehavior.REFLOW,
            surface_refs,
            "Stack regions while preserving task order.",
        ),
        ResponsiveRule(
            "responsive.narrow.actions",
            "narrow",
            ResponsiveBehavior.PRESERVE_ACTION,
            surface_refs,
            "Keep every required primary action reachable.",
        ),
        ResponsiveRule(
            "responsive.narrow.targets",
            "narrow",
            ResponsiveBehavior.TOUCH_TARGET,
            surface_refs,
            "Maintain minimum target sizing and spacing.",
        ),
    )
    if any(
        item.surface_type
        in {
            SurfaceType.DASHBOARD,
            SurfaceType.ADMIN,
            SurfaceType.WORKSPACE,
        }
        for item in architecture.surfaces
    ):
        rules += (
            ResponsiveRule(
                "responsive.narrow.data",
                "narrow",
                ResponsiveBehavior.TABLE_FALLBACK,
                surface_refs,
                "Provide a labeled list/card fallback without dropping data or actions.",
            ),
        )
    responsive = ResponsivePolicy(
        semantic_id("RSP", {"rules": rules, "project": architecture.project_id}),
        breakpoints,
        rules,
        "Support text resize and reflow without two-dimensional scrolling for core tasks.",
        44,
    )
    motion = MotionPolicy(
        semantic_id("MOT", architecture.project_id),
        (
            MotionSpec(
                "motion.feedback",
                MotionPurpose.FEEDBACK,
                "motion.fast",
                "motion.ease",
                "user action result",
                "status feedback",
                "replace movement with immediate state change",
            ),
        ),
    )
    intent_placeholder = ContractRef(
        "design_intent",
        "pending",
        CURRENT_WEB_CONTRACT_VERSION,
        "0" * 64,
    )
    design_system = WebDesignSystemContract(
        contract_version=CURRENT_WEB_CONTRACT_VERSION,
        contract_id="pending",
        project_id=architecture.project_id,
        design_intent_ref=intent_placeholder,
        selected_profile_ref=(None if profile is None else _ref(profile, profile.profile_id)),
        primitive_tokens=primitives,
        semantic_tokens=semantics,
        contrast_pairs=(
            ContrastPairSpec(
                "text.primary.canvas", "text.primary", "surface.canvas", 4.5, "normal text"
            ),
            ContrastPairSpec(
                "text.muted.canvas", "text.muted", "surface.canvas", 4.5, "secondary text"
            ),
            ContrastPairSpec(
                "action.primary",
                "action.primary.foreground",
                "action.primary.background",
                4.5,
                "primary action text",
            ),
        ),
        typography=typography,
        layout=layout,
        responsive=responsive,
        motion=motion,
    )
    return design_system, rules


def _states(*names: ComponentStateName) -> tuple[ComponentStateSpec, ...]:
    return tuple(ComponentStateSpec(name, f"Explicit {name.value} behavior.") for name in names)


def _components_and_surfaces(
    requirements: WebRequirementsContract,
    architecture: WebInformationArchitectureContract,
    rules: tuple[ResponsiveRule, ...],
    design_evidence: tuple[DesignReference, ...],
) -> tuple[tuple[UIComponentSpec, ...], tuple[SurfaceUISpec, ...]]:
    responsive_refs = tuple(item.rule_id for item in rules)
    evidence_refs = tuple(item.design_ref_id for item in design_evidence)
    requirements_by_id = {item.requirement_id: item for item in requirements.requirements}
    components: list[UIComponentSpec] = []
    surfaces: list[SurfaceUISpec] = []
    for surface in architecture.surfaces:
        data_bearing = surface.surface_type in {
            SurfaceType.DASHBOARD,
            SurfaceType.ADMIN,
            SurfaceType.WORKSPACE,
        }
        requirement_text = " ".join(
            requirements_by_id[ref].statement.lower()
            for ref in surface.requirement_refs
            if ref in requirements_by_id
        )
        form_control = any(
            term in requirement_text for term in ("form", "input", "field", "submit")
        )
        modal = surface.surface_type is SurfaceType.MODAL_FLOW
        component_id = semantic_id("UIC", {"surface": surface.surface_id, "data": data_bearing})
        state_names = [ComponentStateName.DEFAULT]
        if data_bearing:
            state_names.extend(
                (ComponentStateName.LOADING, ComponentStateName.EMPTY, ComponentStateName.ERROR)
            )
        if form_control:
            state_names.extend(
                (
                    ComponentStateName.FOCUS_VISIBLE,
                    ComponentStateName.DISABLED,
                    ComponentStateName.READ_ONLY,
                    ComponentStateName.VALIDATION_INVALID,
                    ComponentStateName.VALIDATION_VALID,
                )
            )
        components.append(
            UIComponentSpec(
                component_id=component_id,
                semantic_role="data-view" if data_bearing else "content-region",
                purpose=f"Present the primary content for {surface.name}.",
                surface_refs=(surface.surface_id,),
                variants=(
                    ComponentVariantSpec(
                        "default",
                        "Required baseline treatment.",
                        ("surface.default", "text.primary"),
                    ),
                ),
                states=_states(*state_names),
                interaction=InteractionSpec(
                    "dialog" if modal else "form" if form_control else "region",
                    "content update",
                    "logical reading and control order",
                    "focus follows task order",
                ),
                accessibility=AccessibilitySpec(
                    "derived from approved heading and content",
                    "visible labels for controls",
                    True,
                    True,
                    True,
                    "identify errors with text and status",
                    44,
                    (
                        "move focus into dialog, contain it, then restore trigger focus"
                        if modal
                        else None
                    ),
                ),
                semantic_token_refs=("surface.default", "text.primary"),
                responsive_rule_refs=responsive_refs,
                motion_refs=("motion.feedback",),
                requirement_refs=surface.requirement_refs,
                architecture_refs=(surface.surface_id,),
                data_bearing=data_bearing,
                form_control=form_control,
            )
        )
        action_id = semantic_id("UIC", {"surface": surface.surface_id, "role": "action"})
        components.append(
            UIComponentSpec(
                component_id=action_id,
                semantic_role="primary-action",
                purpose="Execute the approved primary task.",
                surface_refs=(surface.surface_id,),
                variants=(
                    ComponentVariantSpec(
                        "primary",
                        "Single primary action hierarchy.",
                        ("action.primary.background", "action.primary.foreground"),
                    ),
                ),
                states=_states(
                    ComponentStateName.DEFAULT,
                    ComponentStateName.HOVER,
                    ComponentStateName.FOCUS_VISIBLE,
                    ComponentStateName.ACTIVE,
                    ComponentStateName.DISABLED,
                    ComponentStateName.LOADING,
                    ComponentStateName.ERROR,
                    ComponentStateName.SUCCESS,
                ),
                interaction=InteractionSpec(
                    "button",
                    "explicit activation",
                    "Enter or Space activates",
                    "retain visible focus until navigation or completion",
                    primary_action=True,
                ),
                accessibility=AccessibilitySpec(
                    "approved action label",
                    "persistent visible action label",
                    True,
                    True,
                    True,
                    "announce failure and success text",
                    44,
                ),
                semantic_token_refs=(
                    "action.primary.background",
                    "action.primary.foreground",
                    "focus.ring",
                ),
                responsive_rule_refs=responsive_refs,
                motion_refs=("motion.feedback",),
                requirement_refs=surface.requirement_refs,
                architecture_refs=(surface.surface_id,),
            )
        )
        scenarios = ["default", "error"]
        if data_bearing:
            scenarios.extend(("loading", "empty", "partial", "very-long-data"))
        surfaces.append(
            SurfaceUISpec(
                surface_ref=surface.surface_id,
                purpose=f"Specify the approved {surface.name} interaction context.",
                primary_task="Complete the requirement-backed primary task.",
                content_hierarchy=(
                    "primary heading",
                    "primary task content",
                    "supporting context",
                    "status and error messaging",
                ),
                layout_regions=("header", "main", "status"),
                component_refs=(component_id, action_id),
                primary_actions=(action_id,),
                secondary_actions=(),
                state_scenarios=tuple(scenarios),
                responsive_rule_refs=responsive_refs,
                accessibility_requirements=(
                    "visible focus",
                    "logical heading and focus order",
                    "non-color-only status",
                    "resize and reflow",
                ),
                motion_refs=("motion.feedback",),
                design_evidence_refs=evidence_refs,
                requirement_refs=surface.requirement_refs,
                architecture_refs=(surface.surface_id,),
            )
        )
    return tuple(components), tuple(surfaces)


def plan_ui_contracts(
    design_intent: DesignIntent,
    requirements: WebRequirementsContract,
    architecture: WebInformationArchitectureContract,
    selected_profile: ReferenceDesignProfile | None,
    primitive_overrides: tuple[PrimitiveToken, ...],
    design_evidence: tuple[DesignReference, ...],
) -> tuple[WebDesignSystemContract, WebUISpecificationContract]:
    provisional, rules = _foundations(architecture, selected_profile, primitive_overrides)
    intent_ref = _ref(design_intent, design_intent.design_intent_id)
    design_identity = {
        "project": architecture.project_id,
        "intent": intent_ref,
        "profile": provisional.selected_profile_ref,
        "primitive": provisional.primitive_tokens,
        "semantic": provisional.semantic_tokens,
        "typography": provisional.typography,
        "layout": provisional.layout,
        "responsive": provisional.responsive,
        "motion": provisional.motion,
    }
    design_system = WebDesignSystemContract(
        contract_version=CURRENT_WEB_CONTRACT_VERSION,
        contract_id=semantic_id("WDS", design_identity),
        project_id=architecture.project_id,
        design_intent_ref=intent_ref,
        selected_profile_ref=provisional.selected_profile_ref,
        primitive_tokens=provisional.primitive_tokens,
        semantic_tokens=provisional.semantic_tokens,
        contrast_pairs=provisional.contrast_pairs,
        typography=provisional.typography,
        layout=provisional.layout,
        responsive=provisional.responsive,
        motion=provisional.motion,
    )
    components, surfaces = _components_and_surfaces(
        requirements, architecture, rules, design_evidence
    )
    architecture_ref = _ref(architecture, architecture.contract_id)
    design_ref = _ref(design_system, design_system.contract_id)
    ui_identity = {
        "project": architecture.project_id,
        "architecture": architecture_ref,
        "design": design_ref,
        "components": components,
        "surfaces": surfaces,
        "evidence": design_evidence,
    }
    ui = WebUISpecificationContract(
        contract_version=CURRENT_WEB_CONTRACT_VERSION,
        contract_id=semantic_id("WUI", ui_identity),
        project_id=architecture.project_id,
        architecture_ref=architecture_ref,
        design_system_ref=design_ref,
        components=components,
        surfaces=surfaces,
        design_evidence_refs=design_evidence,
    )
    return design_system, ui


__all__ = ("plan_ui_contracts",)
