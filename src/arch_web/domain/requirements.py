"""Atomic and aggregate web requirement contracts."""

from __future__ import annotations

from dataclasses import dataclass

from arch_web.contracts.versions import require_supported_version
from arch_web.domain._base import WebContractRecord, freeze_strings, require_text
from arch_web.domain.enums import (
    RequirementCategory,
    RequirementPriority,
    RequirementStatus,
    WebRoute,
)
from arch_web.domain.errors import WebContractReferenceError, WebContractValidationError
from arch_web.domain.references import EvidenceRef


@dataclass(frozen=True, slots=True)
class WebRequirement(WebContractRecord):
    contract_type = "web_requirement"

    requirement_id: str
    category: RequirementCategory
    statement: str
    priority: RequirementPriority
    source: str
    acceptance_criteria: tuple[str, ...]
    route_requirement: WebRoute
    security_relevance: bool
    status: RequirementStatus
    dependency_refs: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        require_text(self.requirement_id, "requirement_id")
        require_text(self.statement, "statement")
        require_text(self.source, "source")
        object.__setattr__(
            self,
            "acceptance_criteria",
            freeze_strings(self.acceptance_criteria, "acceptance_criteria"),
        )
        object.__setattr__(
            self,
            "dependency_refs",
            freeze_strings(self.dependency_refs, "dependency_refs", sort=True),
        )
        if self.requirement_id in self.dependency_refs:
            raise WebContractReferenceError("A requirement cannot depend on itself")


@dataclass(frozen=True, slots=True)
class WebRequirementsContract(WebContractRecord):
    contract_type = "web_requirements_contract"

    contract_version: str
    contract_id: str
    project_id: str
    route: WebRoute
    requirements: tuple[WebRequirement, ...]
    assumptions: tuple[str, ...] = ()
    exclusions: tuple[str, ...] = ()
    unresolved_items: tuple[str, ...] = ()
    approval_evidence_ref: EvidenceRef | None = None

    def __post_init__(self) -> None:
        require_supported_version(self.contract_version)
        require_text(self.contract_id, "contract_id")
        require_text(self.project_id, "project_id")
        requirements = tuple(sorted(self.requirements, key=lambda item: item.requirement_id))
        ids = tuple(item.requirement_id for item in requirements)
        if len(ids) != len(set(ids)):
            raise WebContractValidationError("requirements contains duplicate IDs")
        known = set(ids)
        for requirement in requirements:
            missing = set(requirement.dependency_refs) - known
            if missing:
                raise WebContractReferenceError(
                    f"Requirement {requirement.requirement_id!r} has missing dependencies: "
                    f"{sorted(missing)!r}"
                )
        object.__setattr__(self, "requirements", requirements)
        for field_name in ("assumptions", "exclusions", "unresolved_items"):
            object.__setattr__(
                self, field_name, freeze_strings(getattr(self, field_name), field_name, sort=True)
            )


__all__ = ("WebRequirement", "WebRequirementsContract")
