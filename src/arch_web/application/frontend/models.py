"""Immutable W06 commands and results."""

from __future__ import annotations

from dataclasses import dataclass

from arch_runtime import ApplyTransitionResult

from arch_web.application.workspace.models import PrepareWorkspaceResult
from arch_web.domain._base import WebContractRecord, freeze_strings, require_text
from arch_web.domain.enums import WebLifecycleStatus
from arch_web.domain.frontend import (
    FrontendAssignmentPacket,
    FrontendCompletionPackage,
    FrontendExecutionAuthorization,
    FrontendImplementationProposal,
)
from arch_web.domain.information_architecture import WebInformationArchitectureContract
from arch_web.domain.references import EvidenceRef
from arch_web.domain.ui_review import UIReviewPackage
from arch_web.domain.ui_specification import WebDesignSystemContract, WebUISpecificationContract
from arch_web.domain.workspace import (
    WorkspaceBaseline,
    WorkspaceExecutionPolicy,
    WorkspaceExecutionReceipt,
    WorkspaceTarget,
)


@dataclass(frozen=True, slots=True)
class PrepareFrontendCommand(WebContractRecord):
    contract_type = "prepare_frontend_command"
    project_id: str
    project_status: WebLifecycleStatus
    runtime_record_version: int
    runtime_record_fingerprint: str
    requirements_fingerprint: str
    architecture: WebInformationArchitectureContract
    design_system: WebDesignSystemContract
    ui_specification: WebUISpecificationContract
    ui_review: UIReviewPackage
    prepared_workspace: PrepareWorkspaceResult
    workspace_receipt: WorkspaceExecutionReceipt
    current_baseline: WorkspaceBaseline
    current_tree_fingerprint: str
    current_git_head: str | None
    selected_unit_refs: tuple[str, ...]

    def __post_init__(self) -> None:
        for name in (
            "project_id",
            "runtime_record_fingerprint",
            "requirements_fingerprint",
            "current_tree_fingerprint",
        ):
            require_text(getattr(self, name), name)
        if self.runtime_record_version < 1:
            raise ValueError("runtime_record_version must be positive")
        if self.current_git_head is not None:
            require_text(self.current_git_head, "current_git_head")
        object.__setattr__(
            self,
            "selected_unit_refs",
            freeze_strings(self.selected_unit_refs, "selected_unit_refs", sort=True),
        )


@dataclass(frozen=True, slots=True)
class PrepareFrontendResult(WebContractRecord):
    contract_type = "prepare_frontend_result"
    assignment: FrontendAssignmentPacket
    execution_workspace: PrepareWorkspaceResult


@dataclass(frozen=True, slots=True)
class AuthorizeFrontendCommand(WebContractRecord):
    contract_type = "authorize_frontend_command"
    prepared: PrepareFrontendResult
    project_status: WebLifecycleStatus
    expected_assignment_fingerprint: str
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
            "expected_assignment_fingerprint",
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
class AuthorizeFrontendResult(WebContractRecord):
    contract_type = "authorize_frontend_result"
    authorization: FrontendExecutionAuthorization
    runtime_result: ApplyTransitionResult


@dataclass(frozen=True, slots=True)
class ApplyFrontendUnitCommand:
    execution_id: str
    project_status: WebLifecycleStatus
    assignment: FrontendAssignmentPacket
    authorization: FrontendExecutionAuthorization
    proposal: FrontendImplementationProposal
    prepared_workspace: PrepareWorkspaceResult
    target: WorkspaceTarget
    policy: WorkspaceExecutionPolicy

    def __post_init__(self) -> None:
        require_text(self.execution_id, "execution_id")


@dataclass(frozen=True, slots=True)
class ApplyFrontendUnitResult:
    proposal: FrontendImplementationProposal
    receipt: WorkspaceExecutionReceipt


@dataclass(frozen=True, slots=True)
class VerifyFrontendCommand:
    project_status: WebLifecycleStatus
    assignment: FrontendAssignmentPacket
    authorization: FrontendExecutionAuthorization
    applied: ApplyFrontendUnitResult
    prepared_workspace: PrepareWorkspaceResult
    required_check_kinds: tuple[str, ...]

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "required_check_kinds",
            freeze_strings(self.required_check_kinds, "required_check_kinds", sort=True),
        )


@dataclass(frozen=True, slots=True)
class VerifyFrontendResult(WebContractRecord):
    contract_type = "verify_frontend_result"
    completion: FrontendCompletionPackage


__all__ = tuple(name for name in globals() if name.endswith(("Command", "Result")))
