"""Immutable W04 commands and results."""

from __future__ import annotations

from dataclasses import dataclass

from arch_runtime import ApplyTransitionResult

from arch_web.domain._base import WebContractRecord, require_text
from arch_web.domain.architecture_review import ArchitectureReviewPackage
from arch_web.domain.design_intent import (
    DesignIntent,
    DesignProfileRecommendation,
    ReferenceDesignProfile,
)
from arch_web.domain.design_tokens import PrimitiveToken
from arch_web.domain.enums import WebLifecycleStatus, WebRoute
from arch_web.domain.information_architecture import WebInformationArchitectureContract
from arch_web.domain.references import DesignReference, EvidenceRef
from arch_web.domain.requirements import WebRequirementsContract
from arch_web.domain.ui_review import DesignCoverageResult, UIReadiness, UIReviewPackage
from arch_web.domain.ui_specification import (
    WebDesignSystemContract,
    WebUISpecificationContract,
)


@dataclass(frozen=True, slots=True)
class PrepareUISpecificationCommand(WebContractRecord):
    contract_type = "prepare_ui_specification_command"

    project_id: str
    project_status: WebLifecycleStatus
    requirements: WebRequirementsContract
    architecture: WebInformationArchitectureContract
    architecture_review: ArchitectureReviewPackage
    expected_requirements_fingerprint: str
    expected_architecture_fingerprint: str
    expected_architecture_review_fingerprint: str
    route: WebRoute
    design_intent: DesignIntent
    selected_profile: ReferenceDesignProfile | None = None
    primitive_overrides: tuple[PrimitiveToken, ...] = ()
    design_evidence: tuple[DesignReference, ...] = ()

    def __post_init__(self) -> None:
        for field_name in (
            "project_id",
            "expected_requirements_fingerprint",
            "expected_architecture_fingerprint",
            "expected_architecture_review_fingerprint",
        ):
            require_text(getattr(self, field_name), field_name)
        object.__setattr__(
            self,
            "primitive_overrides",
            tuple(sorted(self.primitive_overrides, key=lambda item: item.token_id)),
        )
        object.__setattr__(
            self,
            "design_evidence",
            tuple(sorted(self.design_evidence, key=lambda item: item.design_ref_id)),
        )


@dataclass(frozen=True, slots=True)
class PrepareUISpecificationResult(WebContractRecord):
    contract_type = "prepare_ui_specification_result"

    design_intent: DesignIntent
    profile_recommendation: DesignProfileRecommendation
    design_system: WebDesignSystemContract
    ui_specification: WebUISpecificationContract
    coverage: DesignCoverageResult
    review_package: UIReviewPackage


@dataclass(frozen=True, slots=True)
class ApproveUISpecificationCommand(WebContractRecord):
    contract_type = "approve_ui_specification_command"

    project_id: str
    project_status: WebLifecycleStatus
    prepared: PrepareUISpecificationResult
    expected_requirements_fingerprint: str
    expected_architecture_fingerprint: str
    expected_design_intent_fingerprint: str
    expected_profile_fingerprint: str | None
    expected_design_system_fingerprint: str
    expected_ui_specification_fingerprint: str
    expected_coverage_fingerprint: str
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

    def __post_init__(self) -> None:
        for field_name in (
            "project_id",
            "expected_requirements_fingerprint",
            "expected_architecture_fingerprint",
            "expected_design_intent_fingerprint",
            "expected_design_system_fingerprint",
            "expected_ui_specification_fingerprint",
            "expected_coverage_fingerprint",
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
        if self.expected_profile_fingerprint is not None:
            require_text(self.expected_profile_fingerprint, "expected_profile_fingerprint")
        if self.actor_display_name is not None:
            require_text(self.actor_display_name, "actor_display_name")
        if self.expected_record_version < 1:
            raise ValueError("expected_record_version must be positive")


@dataclass(frozen=True, slots=True)
class ApproveUISpecificationResult(WebContractRecord):
    contract_type = "approve_ui_specification_result"

    project_id: str
    approved: bool
    readiness: UIReadiness
    runtime_result: ApplyTransitionResult

    def __post_init__(self) -> None:
        require_text(self.project_id, "project_id")
        if self.approved != (self.readiness is UIReadiness.APPROVED):
            raise ValueError("approved and readiness must agree")


__all__ = (
    "ApproveUISpecificationCommand",
    "ApproveUISpecificationResult",
    "PrepareUISpecificationCommand",
    "PrepareUISpecificationResult",
)
