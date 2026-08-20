"""UI coverage, findings, readiness, and review evidence."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum, unique

from arch_web.contracts.versions import require_supported_version
from arch_web.domain._base import WebContractRecord, freeze_strings, require_text
from arch_web.domain.design_intent import DesignProfileRecommendation
from arch_web.domain.enums import WebRoute
from arch_web.domain.references import ContractRef, EvidenceRef


@unique
class DesignCoverageDisposition(StrEnum):
    SPECIFIED = "specified"
    NOT_APPLICABLE_TO_UI = "not_applicable_to_ui"
    DEFERRED_TO_IMPLEMENTATION = "deferred_to_implementation"
    REQUIRES_EXTERNAL_ASSET = "requires_external_asset"
    UNRESOLVED = "unresolved"


@unique
class DesignCoverageScope(StrEnum):
    REQUIREMENT = "requirement"
    SURFACE = "surface"


@dataclass(frozen=True, slots=True)
class DesignCoverageItem(WebContractRecord):
    contract_type = "design_coverage_item"

    scope: DesignCoverageScope
    target_ref: str
    disposition: DesignCoverageDisposition
    reason: str
    ui_refs: tuple[str, ...] = ()
    target_phase: str | None = None

    def __post_init__(self) -> None:
        require_text(self.target_ref, "target_ref")
        require_text(self.reason, "reason")
        if self.target_phase is not None:
            require_text(self.target_phase, "target_phase")
        deferred = self.disposition is DesignCoverageDisposition.DEFERRED_TO_IMPLEMENTATION
        if deferred != (self.target_phase is not None):
            raise ValueError("Implementation deferral requires exactly one target phase")
        object.__setattr__(self, "ui_refs", freeze_strings(self.ui_refs, "ui_refs", sort=True))


@dataclass(frozen=True, slots=True)
class DesignCoverageResult(WebContractRecord):
    contract_type = "design_coverage_result"

    contract_version: str
    coverage_id: str
    project_id: str
    items: tuple[DesignCoverageItem, ...]

    def __post_init__(self) -> None:
        require_supported_version(self.contract_version)
        require_text(self.coverage_id, "coverage_id")
        require_text(self.project_id, "project_id")
        items = tuple(sorted(self.items, key=lambda item: (item.scope.value, item.target_ref)))
        keys = tuple((item.scope, item.target_ref) for item in items)
        if len(keys) != len(set(keys)):
            raise ValueError("Design coverage targets must be unique")
        object.__setattr__(self, "items", items)


@unique
class DesignFindingSeverity(StrEnum):
    BLOCKING = "blocking"
    ADVISORY = "advisory"


@unique
class DesignFindingCode(StrEnum):
    MISSING_DESIGN_INTENT = "missing_design_intent"
    PROFILE_NOT_EXPLICITLY_ADOPTED = "profile_not_explicitly_adopted"
    STALE_REQUIREMENTS = "stale_requirements"
    STALE_ARCHITECTURE = "stale_architecture"
    UNRESOLVED_SEMANTIC_TOKEN = "unresolved_semantic_token"
    SEMANTIC_ALIAS_CYCLE = "semantic_alias_cycle"
    RAW_TOKEN_BYPASS = "raw_token_bypass"
    INSUFFICIENT_CONTRAST = "insufficient_contrast"
    COLOR_ONLY_MEANING = "color_only_meaning"
    MISSING_FOCUS_VISIBLE = "missing_focus_visible"
    MISSING_KEYBOARD_INTENT = "missing_keyboard_intent"
    MISSING_COMPONENT_STATE = "missing_component_state"
    MISSING_DATA_STATE = "missing_data_state"
    MISSING_SURFACE_UI_SPEC = "missing_surface_ui_spec"
    MISSING_RESPONSIVE_BEHAVIOR = "missing_responsive_behavior"
    REQUIRED_ACTION_HIDDEN = "required_action_hidden"
    MISSING_MODAL_FOCUS_MANAGEMENT = "missing_modal_focus_management"
    MISSING_FORM_SEMANTICS = "missing_form_semantics"
    MISSING_REDUCED_MOTION = "missing_reduced_motion"
    MISSING_DESTRUCTIVE_DISTINCTION = "missing_destructive_distinction"
    UNAUTHORIZED_UI_BEHAVIOR = "unauthorized_ui_behavior"
    UNRESOLVED_UI_REQUIREMENT = "unresolved_ui_requirement"
    CRITICAL_ACCESS_AMBIGUITY = "critical_access_ambiguity"
    COMPETING_PRIMARY_ACTIONS = "competing_primary_actions"
    UNJUSTIFIED_VARIANT = "unjustified_variant"
    UNCONTROLLED_DENSITY = "uncontrolled_density"
    SUBJECTIVE_COHERENCE_ADVISORY = "subjective_coherence_advisory"


@dataclass(frozen=True, slots=True)
class DesignFinding(WebContractRecord):
    contract_type = "design_finding"

    finding_id: str
    code: DesignFindingCode
    severity: DesignFindingSeverity
    message: str
    affected_refs: tuple[str, ...] = ()
    requirement_refs: tuple[str, ...] = ()

    @property
    def blocking(self) -> bool:
        return self.severity is DesignFindingSeverity.BLOCKING

    def __post_init__(self) -> None:
        require_text(self.finding_id, "finding_id")
        require_text(self.message, "message")
        object.__setattr__(
            self, "affected_refs", freeze_strings(self.affected_refs, "affected_refs", sort=True)
        )
        object.__setattr__(
            self,
            "requirement_refs",
            freeze_strings(self.requirement_refs, "requirement_refs", sort=True),
        )


@unique
class UIReadiness(StrEnum):
    NOT_READY = "not_ready"
    READY_FOR_REVIEW = "ready_for_review"
    APPROVED = "approved"


@dataclass(frozen=True, slots=True)
class UIReviewPackage(WebContractRecord):
    contract_type = "ui_review_package"

    contract_version: str
    review_id: str
    project_id: str
    route: WebRoute
    requirements_ref: ContractRef
    architecture_ref: ContractRef
    architecture_review_ref: ContractRef
    design_intent_ref: ContractRef
    selected_profile_ref: ContractRef | None
    profile_recommendation: DesignProfileRecommendation
    design_system_ref: ContractRef
    ui_specification_ref: ContractRef
    coverage_ref: ContractRef
    findings: tuple[DesignFinding, ...]
    unresolved_items: tuple[str, ...]
    readiness: UIReadiness
    approval_evidence_ref: EvidenceRef | None = None

    def __post_init__(self) -> None:
        require_supported_version(self.contract_version)
        require_text(self.review_id, "review_id")
        require_text(self.project_id, "project_id")
        object.__setattr__(
            self, "findings", tuple(sorted(self.findings, key=lambda item: item.finding_id))
        )
        object.__setattr__(
            self,
            "unresolved_items",
            freeze_strings(self.unresolved_items, "unresolved_items", sort=True),
        )
        if (
            any(item.blocking for item in self.findings)
            and self.readiness is not UIReadiness.NOT_READY
        ):
            raise ValueError("Blocking design findings require NOT_READY")
        if self.readiness is UIReadiness.APPROVED and self.approval_evidence_ref is None:
            raise ValueError("APPROVED UI requires approval evidence")


__all__ = (
    "DesignCoverageDisposition",
    "DesignCoverageItem",
    "DesignCoverageResult",
    "DesignCoverageScope",
    "DesignFinding",
    "DesignFindingCode",
    "DesignFindingSeverity",
    "UIReadiness",
    "UIReviewPackage",
)
