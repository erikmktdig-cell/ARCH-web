"""Immutable W08 commands and results."""

from __future__ import annotations

from dataclasses import dataclass

from arch_runtime import ApplyTransitionResult

from arch_web.application.workspace.models import PrepareWorkspaceResult
from arch_web.domain._base import WebContractRecord, freeze_strings, require_text
from arch_web.domain.backend import BackendCompletionPackage, BackendImplementationProposal
from arch_web.domain.enums import WebLifecycleStatus, WebRoute
from arch_web.domain.frontend import FrontendCompletionPackage, FrontendImplementationProposal
from arch_web.domain.information_architecture import WebInformationArchitectureContract
from arch_web.domain.qa import (
    AccessibilityQAEvidence,
    FunctionalQAEvidence,
    IntegrationQAEvidence,
    PerformanceQAEvidence,
    PreviewEnvironmentEvidence,
    PreviewPlan,
    QABaselineProfile,
    QACandidateBaseline,
    QACoverageMatrix,
    QAExecutionAuthorization,
    QAFinding,
    QAReviewPackage,
    QARun,
    QAScope,
    ReleaseReadinessPackage,
    ResponsiveQAEvidence,
    SecurityBehaviorEvidence,
    VisualQAEvidence,
)
from arch_web.domain.references import EvidenceRef
from arch_web.domain.ui_specification import WebDesignSystemContract, WebUISpecificationContract
from arch_web.domain.workspace import WorkspaceBaseline


@dataclass(frozen=True, slots=True)
class PrepareQACommand(WebContractRecord):
    contract_type = "prepare_qa_command"
    project_id: str
    project_status: WebLifecycleStatus
    route: WebRoute
    runtime_record_version: int
    runtime_record_fingerprint: str
    requirements_fingerprint: str
    architecture: WebInformationArchitectureContract
    design_system: WebDesignSystemContract
    ui_specification: WebUISpecificationContract
    prepared_workspace: PrepareWorkspaceResult
    frontend_completion: FrontendCompletionPackage
    frontend_proposal: FrontendImplementationProposal
    backend_completion: BackendCompletionPackage
    backend_proposal: BackendImplementationProposal | None
    current_baseline: WorkspaceBaseline
    profile: QABaselineProfile
    build_artifact_fingerprints: tuple[str, ...]
    workspace_root: str
    entrypoint_path: str
    fixture_id: str
    application_database_path: str | None
    runtime_database_path: str | None

    def __post_init__(self) -> None:
        for name in (
            "project_id",
            "runtime_record_fingerprint",
            "requirements_fingerprint",
            "workspace_root",
            "entrypoint_path",
            "fixture_id",
        ):
            require_text(getattr(self, name), name)
        if self.runtime_record_version < 1:
            raise ValueError("runtime_record_version must be positive")
        object.__setattr__(
            self,
            "build_artifact_fingerprints",
            freeze_strings(
                self.build_artifact_fingerprints, "build_artifact_fingerprints", sort=True
            ),
        )


@dataclass(frozen=True, slots=True)
class PrepareQAResult(WebContractRecord):
    contract_type = "prepare_qa_result"
    candidate: QACandidateBaseline
    scope: QAScope
    preview_plan: PreviewPlan


@dataclass(frozen=True, slots=True)
class AuthorizeTestingCommand(WebContractRecord):
    contract_type = "authorize_testing_command"
    prepared: PrepareQAResult
    project_status: WebLifecycleStatus
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
        for name in (
            "idempotency_key",
            "request_id",
            "transition_key",
            "expected_runtime_state",
            "expected_record_fingerprint",
            "expected_content_fingerprint",
            "actor_id",
        ):
            require_text(getattr(self, name), name)
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
class AuthorizeTestingResult(WebContractRecord):
    contract_type = "authorize_testing_result"
    authorization: QAExecutionAuthorization
    runtime_result: ApplyTransitionResult


@dataclass(frozen=True, slots=True)
class ExecuteQACommand:
    project_status: WebLifecycleStatus
    prepared: PrepareQAResult
    profile: QABaselineProfile
    authorization: QAExecutionAuthorization
    started_at: str
    finished_at: str

    def __post_init__(self) -> None:
        require_text(self.started_at, "started_at")
        require_text(self.finished_at, "finished_at")


@dataclass(frozen=True, slots=True)
class ExecuteQAResult(WebContractRecord):
    contract_type = "execute_qa_result"
    preview: PreviewEnvironmentEvidence
    run: QARun
    functional: FunctionalQAEvidence
    integration: IntegrationQAEvidence
    accessibility: AccessibilityQAEvidence
    responsive: ResponsiveQAEvidence
    visual: VisualQAEvidence
    performance: PerformanceQAEvidence
    security: SecurityBehaviorEvidence
    coverage: QACoverageMatrix
    findings: tuple[QAFinding, ...]
    review: QAReviewPackage

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "findings", tuple(sorted(self.findings, key=lambda item: item.finding_id))
        )


@dataclass(frozen=True, slots=True)
class ApproveReleaseReadinessCommand(WebContractRecord):
    contract_type = "approve_release_readiness_command"
    project_status: WebLifecycleStatus
    prepared: PrepareQAResult
    executed: ExecuteQAResult
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
        for name in (
            "idempotency_key",
            "request_id",
            "transition_key",
            "expected_runtime_state",
            "expected_record_fingerprint",
            "expected_content_fingerprint",
            "actor_id",
        ):
            require_text(getattr(self, name), name)
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
class ApproveReleaseReadinessResult(WebContractRecord):
    contract_type = "approve_release_readiness_result"
    package: ReleaseReadinessPackage
    runtime_result: ApplyTransitionResult


__all__ = tuple(name for name in globals() if name.endswith(("Command", "Result")))
