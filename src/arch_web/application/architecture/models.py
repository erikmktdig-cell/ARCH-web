"""Immutable W03 application commands and results."""

from __future__ import annotations

from dataclasses import dataclass

from arch_runtime import ApplyTransitionResult

from arch_web.domain._base import WebContractRecord, freeze_strings, require_text
from arch_web.domain.architecture_review import ArchitectureReadiness, ArchitectureReviewPackage
from arch_web.domain.enums import WebLifecycleStatus, WebRoute
from arch_web.domain.information_architecture import WebInformationArchitectureContract
from arch_web.domain.navigation import NavigationModel
from arch_web.domain.references import EvidenceRef
from arch_web.domain.requirements import WebRequirementsContract
from arch_web.domain.requirements_review import RequirementsReviewPackage


@dataclass(frozen=True, slots=True)
class PrepareArchitectureCommand(WebContractRecord):
    contract_type = "prepare_architecture_command"

    project_id: str
    project_status: WebLifecycleStatus
    requirements_contract: WebRequirementsContract
    requirements_review: RequirementsReviewPackage
    approved_requirements_fingerprint: str
    approved_requirements_review_fingerprint: str
    route: WebRoute
    assumptions: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for field_name in (
            "project_id",
            "approved_requirements_fingerprint",
            "approved_requirements_review_fingerprint",
        ):
            require_text(getattr(self, field_name), field_name)
        object.__setattr__(
            self, "assumptions", freeze_strings(self.assumptions, "assumptions", sort=True)
        )


@dataclass(frozen=True, slots=True)
class PrepareArchitectureResult(WebContractRecord):
    contract_type = "prepare_architecture_result"

    information_architecture: WebInformationArchitectureContract
    navigation_model: NavigationModel
    review_package: ArchitectureReviewPackage


@dataclass(frozen=True, slots=True)
class ApproveArchitectureCommand(WebContractRecord):
    contract_type = "approve_architecture_command"

    project_id: str
    project_status: WebLifecycleStatus
    prepared: PrepareArchitectureResult
    expected_requirements_fingerprint: str
    expected_architecture_fingerprint: str
    expected_navigation_fingerprint: str
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
            "expected_architecture_fingerprint",
            "expected_navigation_fingerprint",
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
class ApproveArchitectureResult(WebContractRecord):
    contract_type = "approve_architecture_result"

    project_id: str
    approved: bool
    readiness: ArchitectureReadiness
    runtime_result: ApplyTransitionResult

    def __post_init__(self) -> None:
        require_text(self.project_id, "project_id")
        if self.approved != (self.readiness is ArchitectureReadiness.APPROVED):
            raise ValueError("approved and readiness must agree")


__all__ = (
    "ApproveArchitectureCommand",
    "ApproveArchitectureResult",
    "PrepareArchitectureCommand",
    "PrepareArchitectureResult",
)
