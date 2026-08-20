"""Framework-neutral design-system and UI specification contracts."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum, unique

from arch_web.contracts.versions import require_supported_version
from arch_web.domain._base import WebContractRecord, freeze_strings, require_text
from arch_web.domain.design_tokens import ContrastPairSpec, PrimitiveTokenSet, SemanticTokenSet
from arch_web.domain.errors import WebContractReferenceError, WebContractValidationError
from arch_web.domain.references import ContractRef, DesignReference


@dataclass(frozen=True, slots=True)
class TypographyRole(WebContractRecord):
    contract_type = "typography_role"

    role: str
    family_token_ref: str
    size_token_ref: str
    weight_token_ref: str
    line_height_ratio: float
    hierarchy_level: int

    def __post_init__(self) -> None:
        for field_name in ("role", "family_token_ref", "size_token_ref", "weight_token_ref"):
            require_text(getattr(self, field_name), field_name)
        if self.line_height_ratio < 1.0:
            raise WebContractValidationError("Typography line height must be at least 1.0")
        if self.hierarchy_level < 0:
            raise WebContractValidationError("Typography hierarchy must be non-negative")


@dataclass(frozen=True, slots=True)
class TypographySystem(WebContractRecord):
    contract_type = "typography_system"

    typography_id: str
    roles: tuple[TypographyRole, ...]
    paragraph_measure: str
    numeric_treatment: str = "proportional"

    def __post_init__(self) -> None:
        require_text(self.typography_id, "typography_id")
        require_text(self.paragraph_measure, "paragraph_measure")
        require_text(self.numeric_treatment, "numeric_treatment")
        roles = tuple(sorted(self.roles, key=lambda item: (item.hierarchy_level, item.role)))
        names = tuple(item.role for item in roles)
        if len(names) != len(set(names)):
            raise WebContractValidationError("Typography roles must be unique")
        if "body" not in names:
            raise WebContractValidationError("Typography requires a body role")
        object.__setattr__(self, "roles", roles)


@dataclass(frozen=True, slots=True)
class LayoutSystem(WebContractRecord):
    contract_type = "layout_system"

    layout_id: str
    container_strategy: str
    content_max_width_token_ref: str
    gutter_token_ref: str
    stack_gap_token_refs: tuple[str, ...]
    radius_token_refs: tuple[str, ...]
    elevation_token_refs: tuple[str, ...]
    density: str

    def __post_init__(self) -> None:
        for field_name in (
            "layout_id",
            "container_strategy",
            "content_max_width_token_ref",
            "gutter_token_ref",
            "density",
        ):
            require_text(getattr(self, field_name), field_name)
        for field_name in (
            "stack_gap_token_refs",
            "radius_token_refs",
            "elevation_token_refs",
        ):
            object.__setattr__(
                self,
                field_name,
                freeze_strings(getattr(self, field_name), field_name, sort=True),
            )


@unique
class ResponsiveBehavior(StrEnum):
    REFLOW = "reflow"
    NAVIGATION_TRANSFORM = "navigation_transform"
    DENSITY_CHANGE = "density_change"
    TABLE_FALLBACK = "table_fallback"
    DRAWER_MODAL_ADAPT = "drawer_modal_adapt"
    OVERFLOW_MANAGE = "overflow_manage"
    TYPOGRAPHY_SCALE = "typography_scale"
    TOUCH_TARGET = "touch_target"
    PRESERVE_ACTION = "preserve_action"


@dataclass(frozen=True, slots=True)
class BreakpointSpec(WebContractRecord):
    contract_type = "breakpoint_spec"

    breakpoint_id: str
    min_width: int
    max_width: int | None = None

    def __post_init__(self) -> None:
        require_text(self.breakpoint_id, "breakpoint_id")
        if self.min_width < 0 or (self.max_width is not None and self.max_width < self.min_width):
            raise WebContractValidationError("Breakpoint width range is invalid")


@dataclass(frozen=True, slots=True)
class ResponsiveRule(WebContractRecord):
    contract_type = "responsive_rule"

    rule_id: str
    breakpoint_ref: str
    behavior: ResponsiveBehavior
    target_refs: tuple[str, ...]
    description: str
    preserves_required_action: bool = True

    def __post_init__(self) -> None:
        require_text(self.rule_id, "rule_id")
        require_text(self.breakpoint_ref, "breakpoint_ref")
        require_text(self.description, "description")
        object.__setattr__(
            self, "target_refs", freeze_strings(self.target_refs, "target_refs", sort=True)
        )


@dataclass(frozen=True, slots=True)
class ResponsivePolicy(WebContractRecord):
    contract_type = "responsive_policy"

    policy_id: str
    breakpoints: tuple[BreakpointSpec, ...]
    rules: tuple[ResponsiveRule, ...]
    resize_reflow_intent: str
    touch_target_minimum: int

    def __post_init__(self) -> None:
        require_text(self.policy_id, "policy_id")
        require_text(self.resize_reflow_intent, "resize_reflow_intent")
        if self.touch_target_minimum < 24:
            raise WebContractValidationError("Touch target intent must be at least 24px")
        breakpoints = tuple(sorted(self.breakpoints, key=lambda item: item.min_width))
        ids = tuple(item.breakpoint_id for item in breakpoints)
        if len(ids) != len(set(ids)):
            raise WebContractValidationError("Breakpoint IDs must be unique")
        rules = tuple(sorted(self.rules, key=lambda item: item.rule_id))
        known = set(ids)
        if any(item.breakpoint_ref not in known for item in rules):
            raise WebContractReferenceError("Responsive rule references a missing breakpoint")
        object.__setattr__(self, "breakpoints", breakpoints)
        object.__setattr__(self, "rules", rules)


@unique
class MotionPurpose(StrEnum):
    FEEDBACK = "feedback"
    CONTINUITY = "continuity"
    ORIENTATION = "orientation"
    STATUS_CHANGE = "status_change"
    EMPHASIS = "emphasis"


@dataclass(frozen=True, slots=True)
class MotionSpec(WebContractRecord):
    contract_type = "motion_spec"

    motion_id: str
    purpose: MotionPurpose
    duration_token_ref: str
    easing_token_ref: str
    trigger: str
    affected_role: str
    reduced_motion_behavior: str | None
    essential: bool = False

    def __post_init__(self) -> None:
        for field_name in (
            "motion_id",
            "duration_token_ref",
            "easing_token_ref",
            "trigger",
            "affected_role",
        ):
            require_text(getattr(self, field_name), field_name)
        if self.reduced_motion_behavior is not None:
            require_text(self.reduced_motion_behavior, "reduced_motion_behavior")
        if not self.essential and self.reduced_motion_behavior is None:
            raise WebContractValidationError(
                "Non-essential motion requires reduced-motion behavior"
            )


@dataclass(frozen=True, slots=True)
class MotionPolicy(WebContractRecord):
    contract_type = "motion_policy"

    policy_id: str
    motions: tuple[MotionSpec, ...]
    autoplay_decorative_motion: bool = False

    def __post_init__(self) -> None:
        require_text(self.policy_id, "policy_id")
        if self.autoplay_decorative_motion:
            raise WebContractValidationError(
                "Decorative autoplay motion is not an approved default"
            )
        motions = tuple(sorted(self.motions, key=lambda item: item.motion_id))
        if len({item.motion_id for item in motions}) != len(motions):
            raise WebContractValidationError("Motion IDs must be unique")
        object.__setattr__(self, "motions", motions)


@unique
class ComponentStateName(StrEnum):
    DEFAULT = "default"
    HOVER = "hover"
    FOCUS_VISIBLE = "focus-visible"
    ACTIVE = "active"
    SELECTED = "selected"
    DISABLED = "disabled"
    LOADING = "loading"
    EMPTY = "empty"
    ERROR = "error"
    SUCCESS = "success"
    WARNING = "warning"
    VALIDATION_INVALID = "validation-invalid"
    VALIDATION_VALID = "validation-valid"
    EXPANDED = "expanded"
    COLLAPSED = "collapsed"
    CHECKED = "checked"
    UNCHECKED = "unchecked"
    INDETERMINATE = "indeterminate"
    READ_ONLY = "read-only"


@dataclass(frozen=True, slots=True)
class ComponentStateSpec(WebContractRecord):
    contract_type = "component_state_spec"

    state: ComponentStateName
    behavior: str
    semantic_token_refs: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        require_text(self.behavior, "behavior")
        object.__setattr__(
            self,
            "semantic_token_refs",
            freeze_strings(self.semantic_token_refs, "semantic_token_refs", sort=True),
        )


@dataclass(frozen=True, slots=True)
class ComponentVariantSpec(WebContractRecord):
    contract_type = "component_variant_spec"

    variant_id: str
    purpose: str
    semantic_token_refs: tuple[str, ...]

    def __post_init__(self) -> None:
        require_text(self.variant_id, "variant_id")
        require_text(self.purpose, "purpose")
        object.__setattr__(
            self,
            "semantic_token_refs",
            freeze_strings(self.semantic_token_refs, "semantic_token_refs", sort=True),
        )


@dataclass(frozen=True, slots=True)
class InteractionSpec(WebContractRecord):
    contract_type = "interaction_spec"

    pattern_role: str
    trigger_intent: str
    keyboard_intent: str
    focus_intent: str
    primary_action: bool = False
    destructive: bool = False

    def __post_init__(self) -> None:
        for field_name in (
            "pattern_role",
            "trigger_intent",
            "keyboard_intent",
            "focus_intent",
        ):
            require_text(getattr(self, field_name), field_name)


@dataclass(frozen=True, slots=True)
class AccessibilitySpec(WebContractRecord):
    contract_type = "accessibility_spec"

    accessible_name_intent: str
    label_intent: str
    focus_visible: bool
    keyboard_operable: bool
    color_independent: bool
    error_identification: str
    target_size_minimum: int
    focus_management_intent: str | None = None

    def __post_init__(self) -> None:
        for field_name in (
            "accessible_name_intent",
            "label_intent",
            "error_identification",
        ):
            require_text(getattr(self, field_name), field_name)
        if self.focus_management_intent is not None:
            require_text(self.focus_management_intent, "focus_management_intent")
        if self.target_size_minimum < 24:
            raise WebContractValidationError("Accessibility target size must be at least 24px")


@dataclass(frozen=True, slots=True)
class UIComponentSpec(WebContractRecord):
    contract_type = "ui_component_spec"

    component_id: str
    semantic_role: str
    purpose: str
    surface_refs: tuple[str, ...]
    variants: tuple[ComponentVariantSpec, ...]
    states: tuple[ComponentStateSpec, ...]
    interaction: InteractionSpec
    accessibility: AccessibilitySpec
    semantic_token_refs: tuple[str, ...]
    responsive_rule_refs: tuple[str, ...]
    motion_refs: tuple[str, ...]
    requirement_refs: tuple[str, ...]
    architecture_refs: tuple[str, ...]
    data_bearing: bool = False
    form_control: bool = False

    def __post_init__(self) -> None:
        for field_name in ("component_id", "semantic_role", "purpose"):
            require_text(getattr(self, field_name), field_name)
        for field_name in (
            "surface_refs",
            "semantic_token_refs",
            "responsive_rule_refs",
            "motion_refs",
            "requirement_refs",
            "architecture_refs",
        ):
            object.__setattr__(
                self,
                field_name,
                freeze_strings(getattr(self, field_name), field_name, sort=True),
            )
        variants = tuple(sorted(self.variants, key=lambda item: item.variant_id))
        states = tuple(sorted(self.states, key=lambda item: item.state.value))
        if len({item.variant_id for item in variants}) != len(variants):
            raise WebContractValidationError("Component variants must be unique")
        if len({item.state for item in states}) != len(states):
            raise WebContractValidationError("Component states must be unique")
        object.__setattr__(self, "variants", variants)
        object.__setattr__(self, "states", states)


@dataclass(frozen=True, slots=True)
class SurfaceUISpec(WebContractRecord):
    contract_type = "surface_ui_spec"

    surface_ref: str
    purpose: str
    primary_task: str
    content_hierarchy: tuple[str, ...]
    layout_regions: tuple[str, ...]
    component_refs: tuple[str, ...]
    primary_actions: tuple[str, ...]
    secondary_actions: tuple[str, ...]
    state_scenarios: tuple[str, ...]
    responsive_rule_refs: tuple[str, ...]
    accessibility_requirements: tuple[str, ...]
    motion_refs: tuple[str, ...]
    design_evidence_refs: tuple[str, ...]
    requirement_refs: tuple[str, ...]
    architecture_refs: tuple[str, ...]
    unresolved_items: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for field_name in ("surface_ref", "purpose", "primary_task"):
            require_text(getattr(self, field_name), field_name)
        for field_name in (
            "content_hierarchy",
            "layout_regions",
            "component_refs",
            "primary_actions",
            "secondary_actions",
            "state_scenarios",
            "responsive_rule_refs",
            "accessibility_requirements",
            "motion_refs",
            "design_evidence_refs",
            "requirement_refs",
            "architecture_refs",
            "unresolved_items",
        ):
            object.__setattr__(
                self,
                field_name,
                freeze_strings(getattr(self, field_name), field_name, sort=True),
            )


@dataclass(frozen=True, slots=True)
class WebDesignSystemContract(WebContractRecord):
    contract_type = "web_design_system_contract"

    contract_version: str
    contract_id: str
    project_id: str
    design_intent_ref: ContractRef
    selected_profile_ref: ContractRef | None
    primitive_tokens: PrimitiveTokenSet
    semantic_tokens: SemanticTokenSet
    contrast_pairs: tuple[ContrastPairSpec, ...]
    typography: TypographySystem
    layout: LayoutSystem
    responsive: ResponsivePolicy
    motion: MotionPolicy

    def __post_init__(self) -> None:
        require_supported_version(self.contract_version)
        require_text(self.contract_id, "contract_id")
        require_text(self.project_id, "project_id")
        self.semantic_tokens.resolve(self.primitive_tokens)
        pairs = tuple(sorted(self.contrast_pairs, key=lambda item: item.pair_id))
        if len({item.pair_id for item in pairs}) != len(pairs):
            raise WebContractValidationError("Contrast pair IDs must be unique")
        object.__setattr__(self, "contrast_pairs", pairs)


@dataclass(frozen=True, slots=True)
class WebUISpecificationContract(WebContractRecord):
    contract_type = "web_ui_specification_contract"

    contract_version: str
    contract_id: str
    project_id: str
    architecture_ref: ContractRef
    design_system_ref: ContractRef
    components: tuple[UIComponentSpec, ...]
    surfaces: tuple[SurfaceUISpec, ...]
    design_evidence_refs: tuple[DesignReference, ...] = ()

    def __post_init__(self) -> None:
        require_supported_version(self.contract_version)
        require_text(self.contract_id, "contract_id")
        require_text(self.project_id, "project_id")
        components = tuple(sorted(self.components, key=lambda item: item.component_id))
        surfaces = tuple(sorted(self.surfaces, key=lambda item: item.surface_ref))
        if len({item.component_id for item in components}) != len(components):
            raise WebContractValidationError("UI component IDs must be unique")
        if len({item.surface_ref for item in surfaces}) != len(surfaces):
            raise WebContractValidationError("Surface UI specs must be unique")
        known_surfaces = {item.surface_ref for item in surfaces}
        known_components = {item.component_id for item in components}
        for component in components:
            if set(component.surface_refs) - known_surfaces:
                raise WebContractReferenceError("Component references a missing UI surface")
        for surface in surfaces:
            if set(surface.component_refs) - known_components:
                raise WebContractReferenceError("Surface references a missing UI component")
        refs = tuple(sorted(self.design_evidence_refs, key=lambda item: item.design_ref_id))
        object.__setattr__(self, "components", components)
        object.__setattr__(self, "surfaces", surfaces)
        object.__setattr__(self, "design_evidence_refs", refs)


__all__ = (
    "AccessibilitySpec",
    "BreakpointSpec",
    "ComponentStateName",
    "ComponentStateSpec",
    "ComponentVariantSpec",
    "InteractionSpec",
    "LayoutSystem",
    "MotionPolicy",
    "MotionPurpose",
    "MotionSpec",
    "ResponsiveBehavior",
    "ResponsivePolicy",
    "ResponsiveRule",
    "SurfaceUISpec",
    "TypographyRole",
    "TypographySystem",
    "UIComponentSpec",
    "WebDesignSystemContract",
    "WebUISpecificationContract",
)
