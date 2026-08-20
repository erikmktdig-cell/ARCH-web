"""Explicit design intent and small governed reference profiles."""

from __future__ import annotations

from dataclasses import dataclass

from arch_web.contracts.versions import require_supported_version
from arch_web.domain._base import WebContractRecord, freeze_strings, require_text
from arch_web.domain.enums import WebRoute
from arch_web.domain.references import DesignReference


@dataclass(frozen=True, slots=True)
class DesignIntent(WebContractRecord):
    contract_type = "design_intent"

    design_intent_id: str
    project_id: str
    visual_personality: str
    preferred_density: str
    theme_strategy: str
    typography_direction: str
    color_direction: str
    imagery_direction: str
    interaction_character: str
    motion_character: str
    accessibility_priority: str
    brand_attributes: tuple[str, ...] = ()
    brand_constraints: tuple[str, ...] = ()
    reference_refs: tuple[DesignReference, ...] = ()
    explicit_preferences: tuple[str, ...] = ()
    explicit_anti_preferences: tuple[str, ...] = ()
    assumptions: tuple[str, ...] = ()
    unresolved_items: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for field_name in (
            "design_intent_id",
            "project_id",
            "visual_personality",
            "preferred_density",
            "theme_strategy",
            "typography_direction",
            "color_direction",
            "imagery_direction",
            "interaction_character",
            "motion_character",
            "accessibility_priority",
        ):
            require_text(getattr(self, field_name), field_name)
        for field_name in (
            "brand_attributes",
            "brand_constraints",
            "explicit_preferences",
            "explicit_anti_preferences",
            "assumptions",
            "unresolved_items",
        ):
            object.__setattr__(
                self,
                field_name,
                freeze_strings(getattr(self, field_name), field_name, sort=True),
            )
        refs = tuple(sorted(self.reference_refs, key=lambda item: item.design_ref_id))
        if len({item.design_ref_id for item in refs}) != len(refs):
            raise ValueError("reference_refs contains duplicate design references")
        object.__setattr__(self, "reference_refs", refs)


@dataclass(frozen=True, slots=True)
class ReferenceDesignProfile(WebContractRecord):
    contract_type = "reference_design_profile"

    contract_version: str
    profile_id: str
    name: str
    purpose: str
    supported_routes: tuple[WebRoute, ...]
    density: str
    primitive_tokens: tuple[tuple[str, str, str], ...]
    semantic_tokens: tuple[tuple[str, str], ...]
    required_component_states: tuple[str, ...]
    responsive_behaviors: tuple[str, ...]
    motion_defaults: tuple[str, ...]

    def __post_init__(self) -> None:
        require_supported_version(self.contract_version)
        for field_name in ("profile_id", "name", "purpose", "density"):
            require_text(getattr(self, field_name), field_name)
        routes = tuple(sorted(set(self.supported_routes), key=lambda item: item.value))
        if not routes:
            raise ValueError("A reference profile must support at least one route")
        object.__setattr__(self, "supported_routes", routes)
        for field_name in (
            "primitive_tokens",
            "semantic_tokens",
        ):
            values = tuple(sorted(getattr(self, field_name)))
            keys = tuple(item[0] for item in values)
            if len(keys) != len(set(keys)):
                raise ValueError(f"{field_name} contains duplicate roles")
            object.__setattr__(self, field_name, values)
        for field_name in (
            "required_component_states",
            "responsive_behaviors",
            "motion_defaults",
        ):
            object.__setattr__(
                self,
                field_name,
                freeze_strings(getattr(self, field_name), field_name, sort=True),
            )


@dataclass(frozen=True, slots=True)
class DesignProfileRecommendation(WebContractRecord):
    contract_type = "design_profile_recommendation"

    profile_id: str
    reasons: tuple[str, ...]
    route: WebRoute
    requires_explicit_adoption: bool = True

    def __post_init__(self) -> None:
        require_text(self.profile_id, "profile_id")
        object.__setattr__(self, "reasons", freeze_strings(self.reasons, "reasons", sort=True))
        if not self.requires_explicit_adoption:
            raise ValueError("Profile recommendations always require explicit adoption")


__all__ = ("DesignIntent", "DesignProfileRecommendation", "ReferenceDesignProfile")
