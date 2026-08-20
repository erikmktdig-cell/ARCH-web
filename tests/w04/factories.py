"""W04 factories built from exact approved W03 evidence."""

from __future__ import annotations

from arch_web import (
    DesignIntent,
    PrepareUISpecificationCommand,
    WebLifecycleStatus,
    WebRoute,
    get_reference_profile,
    prepare_architecture,
    recommend_reference_profile,
)
from arch_web.domain.design_tokens import PrimitiveToken
from w02.factories import PROJECT_ID
from w03.factories import architecture_command


def design_intent(**changes: object) -> DesignIntent:
    values: dict[str, object] = {
        "design_intent_id": "DIN-governed-neutral",
        "project_id": PROJECT_ID,
        "visual_personality": "calm, clear, and trustworthy",
        "preferred_density": "balanced",
        "theme_strategy": "single accessible light theme",
        "typography_direction": "system-readable hierarchy",
        "color_direction": "high-contrast restrained palette",
        "imagery_direction": "product evidence only",
        "interaction_character": "direct and predictable",
        "motion_character": "restrained feedback",
        "accessibility_priority": "WCAG 2.2 AA design baseline",
        "brand_attributes": ("trustworthy", "clear"),
        "brand_constraints": (),
        "reference_refs": (),
        "explicit_preferences": (),
        "explicit_anti_preferences": ("decorative autoplay motion",),
        "assumptions": (),
        "unresolved_items": (),
    }
    values.update(changes)
    return DesignIntent(**values)  # type: ignore[arg-type]


def design_command(
    route: WebRoute = WebRoute.QUICK,
    *,
    adopt_profile: bool = True,
    overrides: tuple[PrimitiveToken, ...] = (),
    **changes: object,
) -> PrepareUISpecificationCommand:
    upstream_command = architecture_command(route)
    architecture = prepare_architecture(upstream_command)
    recommendation = recommend_reference_profile(architecture.information_architecture, route)
    values: dict[str, object] = {
        "project_id": PROJECT_ID,
        "project_status": WebLifecycleStatus.ARCHITECTURE_APPROVED,
        "requirements": upstream_command.requirements_contract,
        "architecture": architecture.information_architecture,
        "architecture_review": architecture.review_package,
        "expected_requirements_fingerprint": (
            upstream_command.requirements_contract.canonical_fingerprint()
        ),
        "expected_architecture_fingerprint": (
            architecture.information_architecture.canonical_fingerprint()
        ),
        "expected_architecture_review_fingerprint": (
            architecture.review_package.canonical_fingerprint()
        ),
        "route": route,
        "design_intent": design_intent(),
        "selected_profile": (
            get_reference_profile(recommendation.profile_id) if adopt_profile else None
        ),
        "primitive_overrides": overrides,
        "design_evidence": (),
    }
    values.update(changes)
    return PrepareUISpecificationCommand(**values)  # type: ignore[arg-type]
