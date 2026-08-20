"""Immutable findings, route advice, and review evidence."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum, unique

from arch_web.domain._base import (
    WebContractRecord,
    freeze_strings,
    require_text,
    validate_datetime,
)
from arch_web.domain.enums import WebRoute
from arch_web.domain.errors import WebContractValidationError
from arch_web.domain.references import ContractRef, EvidenceRef


@unique
class FindingCode(StrEnum):
    MISSING_PRIMARY_GOAL = "missing_primary_goal"
    AMBIGUOUS_TARGET_USERS = "ambiguous_target_users"
    MISSING_MATERIAL_REQUIREMENT = "missing_material_requirement"
    MISSING_ACCEPTANCE_CRITERIA = "missing_acceptance_criteria"
    UNRESOLVED_AUTH = "unresolved_auth"
    UNRESOLVED_DATA_OWNERSHIP = "unresolved_data_ownership"
    MISSING_ACCESSIBILITY_REQUIREMENT = "missing_accessibility_requirement"
    MISSING_RESPONSIVE_REQUIREMENT = "missing_responsive_requirement"
    MISSING_NAVIGATION_REQUIREMENT = "missing_navigation_requirement"
    MISSING_PERFORMANCE_REQUIREMENT = "missing_performance_requirement"
    MISSING_SECURITY_REQUIREMENT = "missing_security_requirement"
    MISSING_OPERATIONAL_REQUIREMENT = "missing_operational_requirement"
    MISSING_AUDITABILITY_INTENT = "missing_auditability_intent"
    MISSING_FAILURE_RECOVERY_INTENT = "missing_failure_recovery_intent"
    UNRESOLVED_INTEGRATION_DEPENDENCY = "unresolved_integration_dependency"
    CONTRADICTORY_REQUIREMENT = "contradictory_requirement"
    UNRESOLVED_REQUIREMENT_DEPENDENCY = "unresolved_requirement_dependency"
    PROJECT_KIND_INCONSISTENCY = "project_kind_inconsistency"
    PREMATURE_STACK_DECISION = "premature_stack_decision"
    PUBLIC_AUTH_CONFLICT = "public_auth_conflict"
    PERSISTENCE_CONFLICT = "persistence_conflict"
    STATIC_SERVER_CONFLICT = "static_server_conflict"
    THIRD_PARTY_INTEGRATION_CONFLICT = "third_party_integration_conflict"
    ACCEPTANCE_CRITERIA_CONFLICT = "acceptance_criteria_conflict"


@unique
class FindingSeverity(StrEnum):
    ADVISORY = "advisory"
    BLOCKING = "blocking"


@unique
class RequirementsReadiness(StrEnum):
    NOT_READY = "not_ready"
    READY_FOR_REVIEW = "ready_for_review"
    APPROVED = "approved"


@dataclass(frozen=True, slots=True)
class RequirementFinding(WebContractRecord):
    contract_type = "requirement_finding"

    code: FindingCode
    severity: FindingSeverity
    message: str
    requirement_refs: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        require_text(self.message, "message")
        object.__setattr__(
            self,
            "requirement_refs",
            freeze_strings(self.requirement_refs, "requirement_refs", sort=True),
        )


@dataclass(frozen=True, slots=True)
class RouteRecommendation(WebContractRecord):
    contract_type = "route_recommendation"

    recommended_route: WebRoute
    reasons: tuple[str, ...]
    confidence: str
    requires_human_confirmation: bool = True

    def __post_init__(self) -> None:
        object.__setattr__(self, "reasons", freeze_strings(self.reasons, "reasons", sort=True))
        require_text(self.confidence, "confidence")
        if not self.requires_human_confirmation:
            raise WebContractValidationError(
                "Route recommendations always require human confirmation"
            )


@dataclass(frozen=True, slots=True)
class RequirementsReviewPackage(WebContractRecord):
    contract_type = "requirements_review_package"

    contract_version: str
    review_id: str
    project_id: str
    product_brief_ref: ContractRef
    requirements_contract_ref: ContractRef
    gap_findings: tuple[RequirementFinding, ...]
    conflict_findings: tuple[RequirementFinding, ...]
    assumptions: tuple[str, ...]
    exclusions: tuple[str, ...]
    unresolved_items: tuple[str, ...]
    route_recommendation: RouteRecommendation
    readiness: RequirementsReadiness
    source_evidence_refs: tuple[EvidenceRef, ...] = ()
    created_at: datetime | None = None

    def __post_init__(self) -> None:
        from arch_web.contracts.versions import require_supported_version

        require_supported_version(self.contract_version)
        require_text(self.review_id, "review_id")
        require_text(self.project_id, "project_id")
        if self.product_brief_ref.target_contract_type != "web_product_brief":
            raise WebContractValidationError("product_brief_ref has the wrong contract type")
        if self.requirements_contract_ref.target_contract_type != "web_requirements_contract":
            raise WebContractValidationError(
                "requirements_contract_ref has the wrong contract type"
            )
        for field_name in ("gap_findings", "conflict_findings"):
            findings = tuple(
                sorted(
                    getattr(self, field_name),
                    key=lambda item: (item.code.value, item.requirement_refs, item.message),
                )
            )
            object.__setattr__(self, field_name, findings)
        for field_name in ("assumptions", "exclusions", "unresolved_items"):
            object.__setattr__(
                self,
                field_name,
                freeze_strings(getattr(self, field_name), field_name, sort=True),
            )
        refs = tuple(sorted(self.source_evidence_refs, key=lambda item: item.evidence_id))
        if len({item.evidence_id for item in refs}) != len(refs):
            raise WebContractValidationError("source_evidence_refs contains duplicate evidence IDs")
        object.__setattr__(self, "source_evidence_refs", refs)
        validate_datetime(self.created_at, "created_at")
        blockers = any(
            finding.severity is FindingSeverity.BLOCKING
            for finding in (*self.gap_findings, *self.conflict_findings)
        )
        if blockers and self.readiness is not RequirementsReadiness.NOT_READY:
            raise WebContractValidationError("Blocking findings require NOT_READY readiness")
        if self.readiness is RequirementsReadiness.APPROVED:
            raise WebContractValidationError("APPROVED is assigned only after runtime acceptance")


__all__ = (
    "FindingCode",
    "FindingSeverity",
    "RequirementFinding",
    "RequirementsReadiness",
    "RequirementsReviewPackage",
    "RouteRecommendation",
)
