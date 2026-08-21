"""Immutable W05 application commands and results."""

from __future__ import annotations

from dataclasses import dataclass

from arch_runtime import ApplyTransitionResult

from arch_web.domain._base import WebContractRecord, require_text
from arch_web.domain.enums import WebLifecycleStatus
from arch_web.domain.information_architecture import WebInformationArchitectureContract
from arch_web.domain.references import EvidenceRef
from arch_web.domain.requirements import WebRequirementsContract
from arch_web.domain.stack import WebStackProfile
from arch_web.domain.ui_review import UIReviewPackage
from arch_web.domain.ui_specification import WebDesignSystemContract, WebUISpecificationContract
from arch_web.domain.workspace import (
    ImplementationPlan,
    ResolvedStackManifest,
    WorkspaceBaseline,
    WorkspaceChangeSet,
    WorkspaceDryRun,
    WorkspaceExecutionPolicy,
    WorkspaceExecutionReceipt,
    WorkspaceReadiness,
    WorkspaceReviewPackage,
    WorkspaceTarget,
)


@dataclass(frozen=True, slots=True)
class PrepareWorkspaceCommand(WebContractRecord):
    contract_type = "prepare_workspace_command"

    project_id: str
    project_status: WebLifecycleStatus
    requirements: WebRequirementsContract
    architecture: WebInformationArchitectureContract
    design_system: WebDesignSystemContract
    ui_specification: WebUISpecificationContract
    ui_review: UIReviewPackage
    stack_profile: WebStackProfile
    target: WorkspaceTarget
    baseline: WorkspaceBaseline
    policy: WorkspaceExecutionPolicy
    expected_requirements_fingerprint: str
    expected_architecture_fingerprint: str
    expected_design_system_fingerprint: str
    expected_ui_specification_fingerprint: str
    expected_ui_review_fingerprint: str

    def __post_init__(self) -> None:
        for name in (
            "project_id",
            "expected_requirements_fingerprint",
            "expected_architecture_fingerprint",
            "expected_design_system_fingerprint",
            "expected_ui_specification_fingerprint",
            "expected_ui_review_fingerprint",
        ):
            require_text(getattr(self, name), name)


@dataclass(frozen=True, slots=True)
class PrepareWorkspaceResult(WebContractRecord):
    contract_type = "prepare_workspace_result"

    baseline: WorkspaceBaseline
    stack: ResolvedStackManifest
    plan: ImplementationPlan
    change_set: WorkspaceChangeSet
    review: WorkspaceReviewPackage


@dataclass(frozen=True, slots=True)
class ApplyWorkspaceCommand:
    execution_id: str
    target: WorkspaceTarget
    prepared: PrepareWorkspaceResult
    policy: WorkspaceExecutionPolicy
    contents: tuple[tuple[str, bytes], ...] = ()

    def __post_init__(self) -> None:
        require_text(self.execution_id, "execution_id")
        paths = tuple(path for path, _ in self.contents)
        if len(paths) != len(set(paths)):
            raise ValueError("Execution content paths must be unique")


@dataclass(frozen=True, slots=True)
class ApplyWorkspaceResult:
    dry_run: WorkspaceDryRun
    receipt: WorkspaceExecutionReceipt


@dataclass(frozen=True, slots=True)
class ApproveImplementationReadinessCommand(WebContractRecord):
    contract_type = "approve_implementation_readiness_command"

    project_id: str
    project_status: WebLifecycleStatus
    prepared: PrepareWorkspaceResult
    receipt: WorkspaceExecutionReceipt
    expected_requirements_fingerprint: str
    expected_architecture_fingerprint: str
    expected_design_system_fingerprint: str
    expected_ui_specification_fingerprint: str
    expected_ui_review_fingerprint: str
    expected_stack_fingerprint: str
    expected_plan_fingerprint: str
    expected_change_set_fingerprint: str
    expected_receipt_fingerprint: str
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
        for name in (
            "project_id",
            "expected_requirements_fingerprint",
            "expected_architecture_fingerprint",
            "expected_design_system_fingerprint",
            "expected_ui_specification_fingerprint",
            "expected_ui_review_fingerprint",
            "expected_stack_fingerprint",
            "expected_plan_fingerprint",
            "expected_change_set_fingerprint",
            "expected_receipt_fingerprint",
            "idempotency_key",
            "request_id",
            "transition_key",
            "expected_runtime_state",
            "expected_record_fingerprint",
            "expected_content_fingerprint",
            "actor_id",
        ):
            require_text(getattr(self, name), name)
        if self.actor_display_name is not None:
            require_text(self.actor_display_name, "actor_display_name")
        if self.expected_record_version < 1:
            raise ValueError("expected_record_version must be positive")


@dataclass(frozen=True, slots=True)
class ApproveImplementationReadinessResult(WebContractRecord):
    contract_type = "approve_implementation_readiness_result"

    project_id: str
    approved: bool
    readiness: WorkspaceReadiness
    runtime_result: ApplyTransitionResult

    def __post_init__(self) -> None:
        require_text(self.project_id, "project_id")
        if self.approved != (self.readiness is WorkspaceReadiness.APPROVED):
            raise ValueError("approved and readiness must agree")


__all__ = (
    "ApplyWorkspaceCommand",
    "ApplyWorkspaceResult",
    "ApproveImplementationReadinessCommand",
    "ApproveImplementationReadinessResult",
    "PrepareWorkspaceCommand",
    "PrepareWorkspaceResult",
)
