"""Immutable W02 intake, command, and result contracts."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum, unique

from arch_runtime import ApplyTransitionResult

from arch_web.domain._base import WebContractRecord, freeze_strings, require_text
from arch_web.domain.enums import (
    ProjectKind,
    RequirementCategory,
    RequirementPriority,
    WebLifecycleStatus,
    WebRoute,
)
from arch_web.domain.product_brief import WebProductBrief
from arch_web.domain.references import EvidenceRef
from arch_web.domain.requirements import WebRequirementsContract
from arch_web.domain.requirements_review import RequirementsReadiness, RequirementsReviewPackage


@unique
class RequirementSourceKind(StrEnum):
    USER = "user"
    STRUCTURED_NOTES = "structured_notes"
    RESEARCH_EVIDENCE = "research_evidence"
    INHERITED_PROJECT_INTENT = "inherited_project_intent"
    REVIEWER_ASSUMPTION = "reviewer_assumption"


@dataclass(frozen=True, slots=True)
class RequirementSource(WebContractRecord):
    contract_type = "requirement_source"

    source_id: str
    kind: RequirementSourceKind
    label: str
    evidence_ref: EvidenceRef | None = None

    def __post_init__(self) -> None:
        require_text(self.source_id, "source_id")
        require_text(self.label, "label")


@dataclass(frozen=True, slots=True)
class RequirementAnswer(WebContractRecord):
    contract_type = "requirement_answer"

    answer_id: str
    statement: str
    category: RequirementCategory
    priority: RequirementPriority
    source: RequirementSource
    acceptance_criteria: tuple[str, ...] = ()
    dependency_refs: tuple[str, ...] = ()
    security_relevance: bool = False
    inferred: bool = False

    def __post_init__(self) -> None:
        require_text(self.answer_id, "answer_id")
        require_text(self.statement, "statement")
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


@dataclass(frozen=True, slots=True)
class RequirementIntake(WebContractRecord):
    contract_type = "requirement_intake"

    project_id: str
    name: str
    raw_idea: str
    problem_statement: str
    primary_goal: str
    target_users: tuple[str, ...]
    value_proposition: str
    project_kind_hypothesis: ProjectKind
    delivery_mode: str
    route: WebRoute
    answers: tuple[RequirementAnswer, ...]
    core_capabilities: tuple[str, ...] = ()
    content_needs: tuple[str, ...] = ()
    data_needs: tuple[str, ...] = ()
    integrations: tuple[str, ...] = ()
    auth_security_needs: tuple[str, ...] = ()
    responsive_expectations: tuple[str, ...] = ()
    accessibility_expectations: tuple[str, ...] = ()
    performance_expectations: tuple[str, ...] = ()
    operational_expectations: tuple[str, ...] = ()
    constraints: tuple[str, ...] = ()
    assumptions: tuple[str, ...] = ()
    exclusions: tuple[str, ...] = ()
    unresolved_questions: tuple[str, ...] = ()
    source_refs: tuple[EvidenceRef, ...] = ()

    def __post_init__(self) -> None:
        require_text(self.project_id, "project_id")
        require_text(self.name, "name")
        object.__setattr__(self, "answers", tuple(self.answers))
        for field_name in (
            "target_users",
            "core_capabilities",
            "content_needs",
            "data_needs",
            "integrations",
            "auth_security_needs",
            "responsive_expectations",
            "accessibility_expectations",
            "performance_expectations",
            "operational_expectations",
            "constraints",
            "assumptions",
            "exclusions",
            "unresolved_questions",
        ):
            object.__setattr__(self, field_name, tuple(getattr(self, field_name)))
        object.__setattr__(self, "source_refs", tuple(self.source_refs))


@dataclass(frozen=True, slots=True)
class PrepareRequirementsCommand(WebContractRecord):
    contract_type = "prepare_requirements_command"

    intake: RequirementIntake


@dataclass(frozen=True, slots=True)
class PrepareRequirementsResult(WebContractRecord):
    contract_type = "prepare_requirements_result"

    product_brief: WebProductBrief
    requirements_contract: WebRequirementsContract
    review_package: RequirementsReviewPackage


@dataclass(frozen=True, slots=True)
class ApproveRequirementsCommand(WebContractRecord):
    contract_type = "approve_requirements_command"

    project_id: str
    project_status: WebLifecycleStatus
    prepared: PrepareRequirementsResult
    expected_requirements_fingerprint: str
    expected_review_fingerprint: str
    approval_evidence: EvidenceRef
    idempotency_key: str
    request_id: str
    transition_key: str
    expected_runtime_state: str
    expected_record_version: int
    expected_record_fingerprint: str
    expected_content_fingerprint: str
    actor_id: str
    actor_display_name: str | None = None
    expected_workflow_record_version: int | None = None
    expected_workflow_content_fingerprint: str | None = None

    def __post_init__(self) -> None:
        for field_name in (
            "project_id",
            "expected_requirements_fingerprint",
            "expected_review_fingerprint",
            "idempotency_key",
            "request_id",
            "transition_key",
            "expected_runtime_state",
            "expected_record_fingerprint",
            "expected_content_fingerprint",
            "actor_id",
        ):
            require_text(getattr(self, field_name), field_name)
        if self.actor_display_name is not None:
            require_text(self.actor_display_name, "actor_display_name")
        if self.expected_record_version < 1:
            raise ValueError("expected_record_version must be positive")
        if (self.expected_workflow_record_version is None) != (
            self.expected_workflow_content_fingerprint is None
        ):
            raise ValueError("workflow preconditions must be supplied together")
        workflow_fingerprint = self.expected_workflow_content_fingerprint
        if self.expected_workflow_record_version is not None and workflow_fingerprint is not None:
            if self.expected_workflow_record_version < 1:
                raise ValueError("expected_workflow_record_version must be positive")
            require_text(
                workflow_fingerprint,
                "expected_workflow_content_fingerprint",
            )


@dataclass(frozen=True, slots=True)
class ApproveRequirementsResult(WebContractRecord):
    contract_type = "approve_requirements_result"

    project_id: str
    approved: bool
    readiness: RequirementsReadiness
    runtime_result: ApplyTransitionResult

    def __post_init__(self) -> None:
        require_text(self.project_id, "project_id")
        if self.approved != (self.readiness is RequirementsReadiness.APPROVED):
            raise ValueError("approved and readiness must agree")


__all__ = (
    "ApproveRequirementsCommand",
    "ApproveRequirementsResult",
    "PrepareRequirementsCommand",
    "PrepareRequirementsResult",
    "RequirementAnswer",
    "RequirementIntake",
    "RequirementSource",
    "RequirementSourceKind",
)
