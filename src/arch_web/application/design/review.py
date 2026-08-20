"""Pure W04 preparation, coverage, and objective design validation."""

from __future__ import annotations

from arch_web.application.architecture.planning import semantic_id
from arch_web.application.design.errors import UIDesignPreparationError
from arch_web.application.design.models import (
    PrepareUISpecificationCommand,
    PrepareUISpecificationResult,
)
from arch_web.application.design.planning import plan_ui_contracts
from arch_web.application.design.profiles import recommend_reference_profile
from arch_web.application.design.tokens import contrast_ratio, resolved_color_roles
from arch_web.contracts.versions import CURRENT_WEB_CONTRACT_VERSION
from arch_web.domain._base import WebContractRecord
from arch_web.domain.enums import (
    RequirementCategory,
    RequirementPriority,
    SurfaceType,
    WebLifecycleStatus,
    WebRoute,
)
from arch_web.domain.information_architecture import WebInformationArchitectureContract
from arch_web.domain.references import ContractRef
from arch_web.domain.requirements import WebRequirement, WebRequirementsContract
from arch_web.domain.ui_review import (
    DesignCoverageDisposition,
    DesignCoverageItem,
    DesignCoverageResult,
    DesignCoverageScope,
    DesignFinding,
    DesignFindingCode,
    DesignFindingSeverity,
    UIReadiness,
    UIReviewPackage,
)
from arch_web.domain.ui_specification import (
    ComponentStateName,
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


def _requirement_coverage(
    requirement: WebRequirement,
    ui: WebUISpecificationContract,
    design_system: WebDesignSystemContract,
) -> DesignCoverageItem:
    if requirement.priority is RequirementPriority.WONT:
        return DesignCoverageItem(
            DesignCoverageScope.REQUIREMENT,
            requirement.requirement_id,
            DesignCoverageDisposition.NOT_APPLICABLE_TO_UI,
            "Explicitly excluded from approved scope.",
        )
    if requirement.category in {
        RequirementCategory.PERFORMANCE,
        RequirementCategory.OPERATIONAL,
        RequirementCategory.INTEGRATION,
    }:
        return DesignCoverageItem(
            DesignCoverageScope.REQUIREMENT,
            requirement.requirement_id,
            DesignCoverageDisposition.DEFERRED_TO_IMPLEMENTATION,
            "Rendered and operational evidence belongs to implementation validation.",
            target_phase="W06/W07",
        )
    refs = tuple(
        item.surface_ref
        for item in ui.surfaces
        if requirement.requirement_id in item.requirement_refs
    )
    if requirement.category in {
        RequirementCategory.RESPONSIVE,
        RequirementCategory.ACCESSIBILITY,
    }:
        refs = (design_system.responsive.policy_id,)
    if requirement.category in {RequirementCategory.DATA, RequirementCategory.SECURITY}:
        refs = refs or (design_system.contract_id,)
    return DesignCoverageItem(
        DesignCoverageScope.REQUIREMENT,
        requirement.requirement_id,
        (DesignCoverageDisposition.SPECIFIED if refs else DesignCoverageDisposition.UNRESOLVED),
        ("Mapped to explicit UI/design evidence." if refs else "No UI disposition was derived."),
        ui_refs=refs,
    )


def build_design_coverage(
    requirements: WebRequirementsContract,
    architecture: WebInformationArchitectureContract,
    design_system: WebDesignSystemContract,
    ui: WebUISpecificationContract,
) -> DesignCoverageResult:
    items = [
        _requirement_coverage(requirement, ui, design_system)
        for requirement in requirements.requirements
    ]
    ui_by_surface = {item.surface_ref: item for item in ui.surfaces}
    for surface in architecture.surfaces:
        spec = ui_by_surface.get(surface.surface_id)
        items.append(
            DesignCoverageItem(
                DesignCoverageScope.SURFACE,
                surface.surface_id,
                (
                    DesignCoverageDisposition.SPECIFIED
                    if spec is not None
                    else DesignCoverageDisposition.UNRESOLVED
                ),
                (
                    "Surface has an explicit UI specification."
                    if spec is not None
                    else "Required architecture surface has no UI specification."
                ),
                ui_refs=() if spec is None else (spec.surface_ref,),
            )
        )
    identity = {"project": requirements.project_id, "items": items}
    return DesignCoverageResult(
        CURRENT_WEB_CONTRACT_VERSION,
        semantic_id("DCV", identity),
        requirements.project_id,
        tuple(items),
    )


def analyze_ui_design(
    command: PrepareUISpecificationCommand,
    design_system: WebDesignSystemContract,
    ui: WebUISpecificationContract,
    coverage: DesignCoverageResult,
) -> tuple[DesignFinding, ...]:
    findings: list[DesignFinding] = []

    def add(
        code: DesignFindingCode,
        message: str,
        affected: tuple[str, ...] = (),
        requirement_refs: tuple[str, ...] = (),
        severity: DesignFindingSeverity = DesignFindingSeverity.BLOCKING,
    ) -> None:
        findings.append(
            DesignFinding(
                semantic_id(
                    "DFD",
                    {
                        "code": code.value,
                        "affected": affected,
                        "requirements": requirement_refs,
                        "message": message,
                    },
                ),
                code,
                severity,
                message,
                affected,
                requirement_refs,
            )
        )

    if command.selected_profile is None:
        add(
            DesignFindingCode.PROFILE_NOT_EXPLICITLY_ADOPTED,
            "A recommended design profile has not been explicitly adopted.",
        )
    if command.design_intent.unresolved_items:
        add(
            DesignFindingCode.MISSING_DESIGN_INTENT,
            "Material design-intent items remain unresolved.",
            requirement_refs=command.design_intent.unresolved_items,
        )
    required_roles = {
        "text.primary",
        "surface.canvas",
        "surface.default",
        "action.primary.background",
        "action.primary.foreground",
        "focus.ring",
    }
    semantic_roles = {item.role for item in design_system.semantic_tokens.tokens}
    missing_roles = tuple(sorted(required_roles - semantic_roles))
    if missing_roles:
        add(
            DesignFindingCode.UNRESOLVED_SEMANTIC_TOKEN,
            "Required semantic token roles are unresolved.",
            missing_roles,
        )
    colors = resolved_color_roles(design_system.primitive_tokens, design_system.semantic_tokens)
    for pair in design_system.contrast_pairs:
        foreground = colors.get(pair.foreground_role)
        background = colors.get(pair.background_role)
        if foreground is None or background is None:
            add(
                DesignFindingCode.UNRESOLVED_SEMANTIC_TOKEN,
                "Contrast pair references an unresolved color role.",
                (pair.pair_id,),
            )
        elif contrast_ratio(foreground, background) + 1e-9 < pair.minimum_ratio:
            add(
                DesignFindingCode.INSUFFICIENT_CONTRAST,
                f"Contrast pair {pair.pair_id!r} is below {pair.minimum_ratio}:1.",
                (pair.pair_id,),
            )
    semantic_refs = semantic_roles
    responsive_refs = {item.rule_id for item in design_system.responsive.rules}
    motion_refs = {item.motion_id for item in design_system.motion.motions}
    for component in ui.components:
        raw_refs = tuple(
            ref
            for ref in component.semantic_token_refs
            if ref.startswith("#") or ref.endswith("px")
        )
        missing_component_tokens = tuple(
            ref for ref in component.semantic_token_refs if ref not in semantic_refs
        )
        if raw_refs or missing_component_tokens:
            affected_tokens = tuple(sorted({*raw_refs, *missing_component_tokens}))
            add(
                DesignFindingCode.RAW_TOKEN_BYPASS,
                "Component bypasses or cannot resolve semantic token roles.",
                (component.component_id, *affected_tokens),
            )
        states = {item.state for item in component.states}
        interactive_required = {
            ComponentStateName.DEFAULT,
            ComponentStateName.FOCUS_VISIBLE,
            ComponentStateName.DISABLED,
        }
        missing_states = set()
        if component.interaction.pattern_role not in {"region", "static"}:
            missing_states |= interactive_required - states
        if component.data_bearing:
            missing_states |= {
                ComponentStateName.LOADING,
                ComponentStateName.EMPTY,
                ComponentStateName.ERROR,
            } - states
        if component.form_control:
            missing_states |= {
                ComponentStateName.VALIDATION_INVALID,
                ComponentStateName.VALIDATION_VALID,
                ComponentStateName.READ_ONLY,
                ComponentStateName.DISABLED,
            } - states
        if missing_states:
            add(
                (
                    DesignFindingCode.MISSING_DATA_STATE
                    if component.data_bearing
                    else DesignFindingCode.MISSING_COMPONENT_STATE
                ),
                "Applicable component states are missing.",
                (component.component_id, *(item.value for item in sorted(missing_states))),
            )
        if not component.accessibility.focus_visible:
            add(
                DesignFindingCode.MISSING_FOCUS_VISIBLE,
                "Interactive component lacks visible focus intent.",
                (component.component_id,),
            )
        if not component.accessibility.keyboard_operable:
            add(
                DesignFindingCode.MISSING_KEYBOARD_INTENT,
                "Interactive component lacks keyboard-operable intent.",
                (component.component_id,),
            )
        if not component.accessibility.color_independent:
            add(
                DesignFindingCode.COLOR_ONLY_MEANING,
                "Required meaning relies on color alone.",
                (component.component_id,),
            )
        if component.form_control and (
            component.accessibility.label_intent == "placeholder only"
            or component.accessibility.error_identification == "none"
        ):
            add(
                DesignFindingCode.MISSING_FORM_SEMANTICS,
                "Form control lacks persistent label or explicit error semantics.",
                (component.component_id,),
            )
        if set(component.responsive_rule_refs) - responsive_refs:
            add(
                DesignFindingCode.MISSING_RESPONSIVE_BEHAVIOR,
                "Component references missing responsive behavior.",
                (component.component_id,),
            )
        if set(component.motion_refs) - motion_refs:
            add(
                DesignFindingCode.MISSING_REDUCED_MOTION,
                "Component references unresolved motion behavior.",
                (component.component_id,),
            )
        if component.interaction.destructive and not any(
            "destructive" in ref for ref in component.semantic_token_refs
        ):
            add(
                DesignFindingCode.MISSING_DESTRUCTIVE_DISTINCTION,
                "Destructive action lacks differentiated semantic treatment.",
                (component.component_id,),
            )
        if component.interaction.primary_action and not component.requirement_refs:
            add(
                DesignFindingCode.UNAUTHORIZED_UI_BEHAVIOR,
                "Primary action has no approved requirement provenance.",
                (component.component_id,),
            )
    architecture_surfaces = {item.surface_id for item in command.architecture.surfaces}
    ui_surfaces = {item.surface_ref for item in ui.surfaces}
    missing_surfaces = tuple(sorted(architecture_surfaces - ui_surfaces))
    if missing_surfaces:
        add(
            DesignFindingCode.MISSING_SURFACE_UI_SPEC,
            "Required architecture surfaces are missing UI specifications.",
            missing_surfaces,
        )
    for surface in ui.surfaces:
        if len(surface.primary_actions) > 1:
            add(
                DesignFindingCode.COMPETING_PRIMARY_ACTIONS,
                "Surface defines competing primary actions.",
                (surface.surface_ref,),
            )
        if not surface.responsive_rule_refs:
            add(
                DesignFindingCode.MISSING_RESPONSIVE_BEHAVIOR,
                "Surface has no responsive behavior disposition.",
                (surface.surface_ref,),
            )
        architecture_surface = next(
            (
                item
                for item in command.architecture.surfaces
                if item.surface_id == surface.surface_ref
            ),
            None,
        )
        if (
            architecture_surface is not None
            and architecture_surface.surface_type is SurfaceType.MODAL_FLOW
        ):
            surface_components = (
                item for item in ui.components if surface.surface_ref in item.surface_refs
            )
            if not any(
                item.interaction.pattern_role == "dialog"
                and item.accessibility.focus_management_intent is not None
                for item in surface_components
            ):
                add(
                    DesignFindingCode.MISSING_MODAL_FOCUS_MANAGEMENT,
                    "Modal surface lacks explicit dialog focus management.",
                    (surface.surface_ref,),
                )
    hidden_actions = tuple(
        item.rule_id
        for item in design_system.responsive.rules
        if not item.preserves_required_action
    )
    if hidden_actions:
        add(
            DesignFindingCode.REQUIRED_ACTION_HIDDEN,
            "Responsive behavior hides required functionality.",
            hidden_actions,
        )
    unresolved_coverage = tuple(
        item.target_ref
        for item in coverage.items
        if item.disposition is DesignCoverageDisposition.UNRESOLVED
    )
    if unresolved_coverage:
        add(
            DesignFindingCode.UNRESOLVED_UI_REQUIREMENT,
            "UI coverage contains unresolved material targets.",
            unresolved_coverage,
        )
    if command.route is WebRoute.CRITICAL:
        sensitive = any(
            item.category is RequirementCategory.SECURITY and item.security_relevance
            for item in command.requirements.requirements
        )
        protected = any(
            item.surface_type in {SurfaceType.ADMIN, SurfaceType.SETTINGS}
            or item.auth_requirement == "required"
            for item in command.architecture.surfaces
        )
        if sensitive and not protected:
            add(
                DesignFindingCode.CRITICAL_ACCESS_AMBIGUITY,
                "Critical sensitive-data presentation lacks an explicit protected surface.",
            )
    return tuple(sorted(findings, key=lambda item: item.finding_id))


def _verify_upstream(command: PrepareUISpecificationCommand) -> None:
    if command.project_status is not WebLifecycleStatus.ARCHITECTURE_APPROVED:
        raise UIDesignPreparationError("UI preparation requires ARCHITECTURE_APPROVED")
    project_ids = {
        command.requirements.project_id,
        command.architecture.project_id,
        command.architecture_review.project_id,
        command.design_intent.project_id,
    }
    if project_ids != {command.project_id}:
        raise UIDesignPreparationError("UI preparation project identity mismatch")
    bindings = (
        (
            command.requirements.canonical_fingerprint(),
            command.expected_requirements_fingerprint,
            "Requirements",
        ),
        (
            command.architecture.canonical_fingerprint(),
            command.expected_architecture_fingerprint,
            "Architecture",
        ),
        (
            command.architecture_review.canonical_fingerprint(),
            command.expected_architecture_review_fingerprint,
            "Architecture review",
        ),
    )
    for actual, expected, label in bindings:
        if actual != expected:
            raise UIDesignPreparationError(f"{label} fingerprint is stale")
    command.architecture_review.requirements_contract_ref.verify(
        command.requirements, command.requirements.contract_id
    )
    command.architecture_review.information_architecture_ref.verify(
        command.architecture, command.architecture.contract_id
    )
    if (
        command.route is not command.requirements.route
        or command.route is not command.architecture_review.route
    ):
        raise UIDesignPreparationError("Authoritative route mismatch")
    if (
        command.selected_profile is not None
        and command.route not in command.selected_profile.supported_routes
    ):
        raise UIDesignPreparationError("Selected design profile does not support the route")


def prepare_ui_specification(
    command: PrepareUISpecificationCommand,
) -> PrepareUISpecificationResult:
    _verify_upstream(command)
    recommendation = recommend_reference_profile(command.architecture, command.route)
    design_system, ui = plan_ui_contracts(
        command.design_intent,
        command.requirements,
        command.architecture,
        command.selected_profile,
        command.primitive_overrides,
        command.design_evidence,
    )
    coverage = build_design_coverage(command.requirements, command.architecture, design_system, ui)
    findings = analyze_ui_design(command, design_system, ui, coverage)
    blockers = any(item.blocking for item in findings)
    selected_profile_ref = (
        None
        if command.selected_profile is None
        else _ref(command.selected_profile, command.selected_profile.profile_id)
    )
    review_identity = {
        "requirements": command.expected_requirements_fingerprint,
        "architecture": command.expected_architecture_fingerprint,
        "architecture_review": command.expected_architecture_review_fingerprint,
        "intent": command.design_intent.canonical_fingerprint(),
        "profile": selected_profile_ref,
        "design_system": design_system.canonical_fingerprint(),
        "ui": ui.canonical_fingerprint(),
        "coverage": coverage.canonical_fingerprint(),
        "findings": findings,
    }
    review = UIReviewPackage(
        contract_version=CURRENT_WEB_CONTRACT_VERSION,
        review_id=semantic_id("URV", review_identity),
        project_id=command.project_id,
        route=command.route,
        requirements_ref=_ref(command.requirements, command.requirements.contract_id),
        architecture_ref=_ref(command.architecture, command.architecture.contract_id),
        architecture_review_ref=_ref(
            command.architecture_review, command.architecture_review.review_id
        ),
        design_intent_ref=_ref(command.design_intent, command.design_intent.design_intent_id),
        selected_profile_ref=selected_profile_ref,
        profile_recommendation=recommendation,
        design_system_ref=_ref(design_system, design_system.contract_id),
        ui_specification_ref=_ref(ui, ui.contract_id),
        coverage_ref=_ref(coverage, coverage.coverage_id),
        findings=findings,
        unresolved_items=command.design_intent.unresolved_items,
        readiness=UIReadiness.NOT_READY if blockers else UIReadiness.READY_FOR_REVIEW,
    )
    return PrepareUISpecificationResult(
        command.design_intent,
        recommendation,
        design_system,
        ui,
        coverage,
        review,
    )


__all__ = ("analyze_ui_design", "build_design_coverage", "prepare_ui_specification")
