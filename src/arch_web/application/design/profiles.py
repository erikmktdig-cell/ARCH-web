"""Small immutable reference-profile registry and advisory recommendation."""

from __future__ import annotations

from arch_web.contracts.versions import CURRENT_WEB_CONTRACT_VERSION
from arch_web.domain.design_intent import (
    DesignProfileRecommendation,
    ReferenceDesignProfile,
)
from arch_web.domain.enums import SurfaceType, WebRoute
from arch_web.domain.information_architecture import WebInformationArchitectureContract

_PRIMITIVES = (
    ("color.canvas", "color", "#FFFFFF"),
    ("color.ink", "color", "#111827"),
    ("color.muted", "color", "#4B5563"),
    ("color.action", "color", "#005FCC"),
    ("color.danger", "color", "#B42318"),
    ("color.success", "color", "#16794B"),
    ("color.warning", "color", "#8A4B00"),
    ("font.family.body", "font_family", "system-ui, sans-serif"),
    ("font.size.body", "font_size", "16px"),
    ("font.size.heading", "font_size", "32px"),
    ("font.weight.regular", "font_weight", "400"),
    ("font.weight.strong", "font_weight", "700"),
    ("space.2", "spacing", "8px"),
    ("space.4", "spacing", "16px"),
    ("space.6", "spacing", "24px"),
    ("layout.content.max", "spacing", "1200px"),
    ("radius.control", "radius", "6px"),
    ("elevation.raised", "elevation", "0 2px 8px rgba(0,0,0,0.16)"),
    ("motion.fast", "motion_duration", "120ms"),
    ("motion.standard", "motion_duration", "200ms"),
    ("motion.ease", "motion_easing", "ease-out"),
)
_SEMANTICS = (
    ("action.destructive.background", "color.danger"),
    ("action.destructive.foreground", "color.canvas"),
    ("action.primary.background", "color.action"),
    ("action.primary.foreground", "color.canvas"),
    ("border.default", "color.muted"),
    ("focus.ring", "color.action"),
    ("state.error.foreground", "color.danger"),
    ("state.success.foreground", "color.success"),
    ("state.warning.foreground", "color.warning"),
    ("surface.canvas", "color.canvas"),
    ("surface.default", "surface.canvas"),
    ("text.muted", "color.muted"),
    ("text.primary", "color.ink"),
)
_STATES = (
    "default",
    "hover",
    "focus-visible",
    "active",
    "disabled",
    "loading",
    "empty",
    "error",
)
_RESPONSIVE = (
    "layout reflow",
    "navigation transformation",
    "preserve required actions",
    "touch target intent",
)
_MOTION = ("feedback with reduced-motion alternative",)


def reference_design_profiles() -> tuple[ReferenceDesignProfile, ...]:
    common = {
        "contract_version": CURRENT_WEB_CONTRACT_VERSION,
        "supported_routes": tuple(WebRoute),
        "primitive_tokens": _PRIMITIVES,
        "semantic_tokens": _SEMANTICS,
        "required_component_states": _STATES,
        "responsive_behaviors": _RESPONSIVE,
        "motion_defaults": _MOTION,
    }
    return (
        ReferenceDesignProfile(
            profile_id="content_marketing_neutral",
            name="Content Marketing Neutral",
            purpose="Accessible content and product-marketing surfaces.",
            density="comfortable",
            **common,  # type: ignore[arg-type]
        ),
        ReferenceDesignProfile(
            profile_id="dense_operational_neutral",
            name="Dense Operational Neutral",
            purpose="Accessible admin and data-dense operational surfaces.",
            density="compact",
            **common,  # type: ignore[arg-type]
        ),
        ReferenceDesignProfile(
            profile_id="modern_product_neutral",
            name="Modern Product Neutral",
            purpose="Accessible application and dashboard surfaces.",
            density="balanced",
            **common,  # type: ignore[arg-type]
        ),
    )


def get_reference_profile(profile_id: str) -> ReferenceDesignProfile:
    for profile in reference_design_profiles():
        if profile.profile_id == profile_id:
            return profile
    raise KeyError(profile_id)


def recommend_reference_profile(
    architecture: WebInformationArchitectureContract, route: WebRoute
) -> DesignProfileRecommendation:
    surface_types = {item.surface_type for item in architecture.surfaces}
    if surface_types & {SurfaceType.ADMIN, SurfaceType.SETTINGS}:
        profile_id = "dense_operational_neutral"
        reason = "Operational surfaces benefit from controlled compact density."
    elif surface_types & {SurfaceType.DASHBOARD, SurfaceType.WORKSPACE}:
        profile_id = "modern_product_neutral"
        reason = "Application surfaces require a balanced interaction baseline."
    else:
        profile_id = "content_marketing_neutral"
        reason = "Content-led surfaces require readable hierarchy and comfortable density."
    return DesignProfileRecommendation(
        profile_id=profile_id,
        reasons=(reason,),
        route=route,
    )


__all__ = (
    "get_reference_profile",
    "recommend_reference_profile",
    "reference_design_profiles",
)
