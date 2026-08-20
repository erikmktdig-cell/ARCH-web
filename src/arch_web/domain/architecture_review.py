"""Information-architecture coverage, findings, and review evidence."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum, unique

from arch_web.contracts.versions import require_supported_version
from arch_web.domain._base import WebContractRecord, freeze_strings, require_text
from arch_web.domain.enums import WebRoute
from arch_web.domain.references import ContractRef, EvidenceRef


@unique
class CoverageDisposition(StrEnum):
    COVERED = "covered"
    NOT_APPLICABLE_TO_IA = "not_applicable_to_ia"
    DEFERRED_TO_W04 = "deferred_to_w04"
    DEFERRED_TO_W06_W07 = "deferred_to_w06_w07"
    UNRESOLVED = "unresolved"


@unique
class ArchitectureFindingSeverity(StrEnum):
    BLOCKING = "blocking"
    WARNING = "warning"
    INFO = "info"


@unique
class ArchitectureFindingCode(StrEnum):
    MISSING_PROVENANCE = "missing_provenance"
    MISSING_SURFACE = "missing_surface"
    DUPLICATE_PATH = "duplicate_path"
    PUBLIC_PROTECTED_MISMATCH = "public_protected_mismatch"
    UNAPPROVED_AUTH_INTENT = "unapproved_auth_intent"
    MISSING_PUBLIC_ENTRY = "missing_public_entry"
    UNCOVERED_REQUIREMENT = "uncovered_requirement"
    NAVIGATION_CYCLE = "navigation_cycle"
    UNREACHABLE_SURFACE = "unreachable_surface"
    UNJUSTIFIED_DYNAMIC_PARAMETER = "unjustified_dynamic_parameter"
    PROJECT_MISMATCH = "project_mismatch"
    STALE_REQUIREMENTS = "stale_requirements"
    UNAPPROVED_BACKEND_DATA = "unapproved_backend_data"
    CONTRADICTS_EXCLUSION = "contradicts_exclusion"
    INSUFFICIENT_ROUTE_EVIDENCE = "insufficient_route_evidence"


@unique
class ArchitectureReadiness(StrEnum):
    NOT_READY = "not_ready"
    READY_FOR_REVIEW = "ready_for_review"
    APPROVED = "approved"


@dataclass(frozen=True, slots=True)
class RequirementCoverage(WebContractRecord):
    contract_type = "requirement_coverage"

    requirement_ref: str
    disposition: CoverageDisposition
    reason: str
    target_phase: str | None = None
    architecture_refs: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        require_text(self.requirement_ref, "requirement_ref")
        require_text(self.reason, "reason")
        if self.target_phase is not None:
            require_text(self.target_phase, "target_phase")
        deferred = self.disposition in {
            CoverageDisposition.DEFERRED_TO_W04,
            CoverageDisposition.DEFERRED_TO_W06_W07,
        }
        if deferred != (self.target_phase is not None):
            raise ValueError("Deferred coverage requires exactly one target phase")
        object.__setattr__(
            self,
            "architecture_refs",
            freeze_strings(self.architecture_refs, "architecture_refs", sort=True),
        )


@dataclass(frozen=True, slots=True)
class ArchitectureFinding(WebContractRecord):
    contract_type = "architecture_finding"

    finding_id: str
    code: ArchitectureFindingCode
    severity: ArchitectureFindingSeverity
    message: str
    affected_refs: tuple[str, ...] = ()
    requirement_refs: tuple[str, ...] = ()

    @property
    def blocking(self) -> bool:
        return self.severity is ArchitectureFindingSeverity.BLOCKING

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


@dataclass(frozen=True, slots=True)
class ArchitectureReviewPackage(WebContractRecord):
    contract_type = "architecture_review_package"

    contract_version: str
    review_id: str
    project_id: str
    requirements_contract_ref: ContractRef
    requirements_review_ref: ContractRef
    information_architecture_ref: ContractRef
    navigation_model_ref: ContractRef
    route: WebRoute
    coverage: tuple[RequirementCoverage, ...]
    findings: tuple[ArchitectureFinding, ...]
    assumptions: tuple[str, ...]
    readiness: ArchitectureReadiness
    approval_evidence_ref: EvidenceRef | None = None

    def __post_init__(self) -> None:
        require_supported_version(self.contract_version)
        require_text(self.review_id, "review_id")
        require_text(self.project_id, "project_id")
        object.__setattr__(
            self, "coverage", tuple(sorted(self.coverage, key=lambda x: x.requirement_ref))
        )
        object.__setattr__(
            self, "findings", tuple(sorted(self.findings, key=lambda x: x.finding_id))
        )
        object.__setattr__(
            self,
            "assumptions",
            freeze_strings(self.assumptions, "assumptions", sort=True),
        )
        has_blockers = any(item.blocking for item in self.findings)
        if has_blockers and self.readiness is not ArchitectureReadiness.NOT_READY:
            raise ValueError("Blocking findings require NOT_READY")
        if self.readiness is ArchitectureReadiness.APPROVED and self.approval_evidence_ref is None:
            raise ValueError("APPROVED architecture requires approval evidence")


__all__ = (
    "ArchitectureFinding",
    "ArchitectureFindingCode",
    "ArchitectureFindingSeverity",
    "ArchitectureReadiness",
    "ArchitectureReviewPackage",
    "CoverageDisposition",
    "RequirementCoverage",
)
