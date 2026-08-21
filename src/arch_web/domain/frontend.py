"""Immutable W06 frontend engineering contracts."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum, unique

from arch_web.contracts.versions import require_supported_version
from arch_web.domain._base import (
    WebContractRecord,
    freeze_string_map,
    freeze_strings,
    require_text,
)
from arch_web.domain.enums import WebLifecycleStatus
from arch_web.domain.references import ContractRef
from arch_web.domain.workspace import ReconciliationStatus, WorkspaceExecutionReceipt


@unique
class FrontendArtifactKind(StrEnum):
    SOURCE = "source"
    STYLE = "style"
    TEST = "test"
    ASSET = "asset"
    MANIFEST = "manifest"


@unique
class FrontendDataDisposition(StrEnum):
    STATIC = "static"
    TYPED_BOUNDARY = "typed_boundary"
    TEST_FIXTURE = "test_fixture"
    PENDING_BACKEND_BINDING = "pending_backend_binding"


@unique
class FrontendCheckStatus(StrEnum):
    PASS = "pass"
    FAIL = "fail"
    INCONCLUSIVE = "inconclusive"
    NOT_APPLICABLE = "not_applicable"


@unique
class FrontendFindingCode(StrEnum):
    WRONG_LIFECYCLE = "wrong_lifecycle"
    STALE_EVIDENCE = "stale_evidence"
    UNAUTHORIZED_UNIT = "unauthorized_unit"
    PATH_CLAIM_VIOLATION = "path_claim_violation"
    UNKNOWN_ARTIFACT = "unknown_artifact"
    TRACEABILITY_GAP = "traceability_gap"
    DESIGN_DRIFT = "design_drift"
    ARCHITECTURE_DRIFT = "architecture_drift"
    MISSING_STATE = "missing_state"
    TOKEN_BYPASS = "token_bypass"
    RESPONSIVE_GAP = "responsive_gap"
    ACCESSIBILITY_GAP = "accessibility_gap"
    INVENTED_BACKEND = "invented_backend"
    PRODUCTION_MOCK = "production_mock"
    UNAPPROVED_DEPENDENCY = "unapproved_dependency"
    FLOATING_DEPENDENCY = "floating_dependency"
    CLIENT_SECRET = "client_secret"
    UNSAFE_SCRIPT = "unsafe_script"
    HIDDEN_TRACKING = "hidden_tracking"
    CHECK_FAILED = "check_failed"
    MISSING_CHECK = "missing_check"
    RECONCILIATION_REQUIRED = "reconciliation_required"
    BEHAVIOR_CHANGING_ASSUMPTION = "behavior_changing_assumption"
    UNSUPPORTED_FRONTEND_STACK = "unsupported_frontend_stack"


@unique
class FrontendReadiness(StrEnum):
    BLOCKED = "blocked"
    COMPLETE_FOR_REVIEW = "complete_for_review"


def _sorted_unique_records[T](
    values: tuple[T, ...], key: Callable[[T], str], label: str
) -> tuple[T, ...]:
    ordered = tuple(sorted(values, key=key))
    keys = tuple(key(item) for item in ordered)
    if len(keys) != len(set(keys)):
        raise ValueError(f"{label} must be unique")
    return ordered


@dataclass(frozen=True, slots=True)
class FrontendExecutionAuthorization(WebContractRecord):
    contract_type = "frontend_execution_authorization"

    contract_version: str
    authorization_id: str
    project_id: str
    assignment_fingerprint: str
    implementation_plan_fingerprint: str
    workspace_receipt_fingerprint: str
    runtime_record_version: int
    runtime_record_fingerprint: str
    authorized: bool

    def __post_init__(self) -> None:
        require_supported_version(self.contract_version)
        for name in (
            "authorization_id",
            "project_id",
            "assignment_fingerprint",
            "implementation_plan_fingerprint",
            "workspace_receipt_fingerprint",
            "runtime_record_fingerprint",
        ):
            require_text(getattr(self, name), name)
        if self.runtime_record_version < 1:
            raise ValueError("runtime_record_version must be positive")


@dataclass(frozen=True, slots=True)
class FrontendAssignmentPacket(WebContractRecord):
    contract_type = "frontend_assignment_packet"

    contract_version: str
    assignment_id: str
    project_id: str
    runtime_state: WebLifecycleStatus
    runtime_record_version: int
    runtime_record_fingerprint: str
    requirements_fingerprint: str
    architecture_fingerprint: str
    design_system_fingerprint: str
    ui_specification_fingerprint: str
    ui_review_fingerprint: str
    stack_fingerprint: str
    implementation_plan_fingerprint: str
    workspace_receipt_fingerprint: str
    managed_tree_fingerprint: str
    git_head: str | None
    selected_unit_refs: tuple[str, ...]
    path_claim_refs: tuple[str, ...]
    surface_refs: tuple[str, ...]
    route_refs: tuple[str, ...]
    route_paths: tuple[tuple[str, str], ...]
    component_refs: tuple[str, ...]
    component_state_refs: tuple[str, ...]
    responsive_rule_refs: tuple[str, ...]
    semantic_token_refs: tuple[str, ...]
    expected_evidence: tuple[str, ...]
    prohibited_scope: tuple[str, ...]
    stop_conditions: tuple[str, ...]

    def __post_init__(self) -> None:
        require_supported_version(self.contract_version)
        for name in (
            "assignment_id",
            "project_id",
            "runtime_record_fingerprint",
            "requirements_fingerprint",
            "architecture_fingerprint",
            "design_system_fingerprint",
            "ui_specification_fingerprint",
            "ui_review_fingerprint",
            "stack_fingerprint",
            "implementation_plan_fingerprint",
            "workspace_receipt_fingerprint",
            "managed_tree_fingerprint",
        ):
            require_text(getattr(self, name), name)
        if self.runtime_state is not WebLifecycleStatus.IMPLEMENTATION_READY:
            raise ValueError("Frontend assignment requires IMPLEMENTATION_READY")
        if self.runtime_record_version < 1:
            raise ValueError("runtime_record_version must be positive")
        if self.git_head is not None:
            require_text(self.git_head, "git_head")
        for name in (
            "selected_unit_refs",
            "path_claim_refs",
            "surface_refs",
            "route_refs",
            "component_refs",
            "component_state_refs",
            "responsive_rule_refs",
            "semantic_token_refs",
            "expected_evidence",
            "prohibited_scope",
            "stop_conditions",
        ):
            object.__setattr__(self, name, freeze_strings(getattr(self, name), name, sort=True))
        object.__setattr__(self, "route_paths", freeze_string_map(self.route_paths, "route_paths"))
        if not self.selected_unit_refs or not self.path_claim_refs:
            raise ValueError("Frontend assignment requires units and path claims")


@dataclass(frozen=True, slots=True)
class FrontendArtifact(WebContractRecord):
    contract_type = "frontend_artifact"

    artifact_id: str
    unit_ref: str
    path: str
    kind: FrontendArtifactKind
    content: str
    content_fingerprint: str
    claim_ref: str

    def __post_init__(self) -> None:
        for name in ("artifact_id", "unit_ref", "path", "content_fingerprint", "claim_ref"):
            require_text(getattr(self, name), name)
        if not self.content:
            raise ValueError("Frontend artifact content must not be empty")


@dataclass(frozen=True, slots=True)
class FrontendSurfaceBinding(WebContractRecord):
    contract_type = "frontend_surface_binding"
    surface_ref: str
    artifact_refs: tuple[str, ...]

    def __post_init__(self) -> None:
        require_text(self.surface_ref, "surface_ref")
        object.__setattr__(
            self, "artifact_refs", freeze_strings(self.artifact_refs, "artifact_refs", sort=True)
        )


@dataclass(frozen=True, slots=True)
class FrontendRouteBinding(WebContractRecord):
    contract_type = "frontend_route_binding"
    route_ref: str
    path: str
    artifact_ref: str

    def __post_init__(self) -> None:
        for name in ("route_ref", "path", "artifact_ref"):
            require_text(getattr(self, name), name)


@dataclass(frozen=True, slots=True)
class FrontendComponentBinding(WebContractRecord):
    contract_type = "frontend_component_binding"
    component_ref: str
    artifact_refs: tuple[str, ...]
    implemented_states: tuple[str, ...]
    responsive_rule_refs: tuple[str, ...]
    accessibility_evidence: tuple[str, ...]

    def __post_init__(self) -> None:
        require_text(self.component_ref, "component_ref")
        for name in (
            "artifact_refs",
            "implemented_states",
            "responsive_rule_refs",
            "accessibility_evidence",
        ):
            object.__setattr__(self, name, freeze_strings(getattr(self, name), name, sort=True))


@dataclass(frozen=True, slots=True)
class FrontendDataBinding(WebContractRecord):
    contract_type = "frontend_data_binding"
    binding_id: str
    component_ref: str
    disposition: FrontendDataDisposition
    boundary_name: str | None = None

    def __post_init__(self) -> None:
        require_text(self.binding_id, "binding_id")
        require_text(self.component_ref, "component_ref")
        if self.boundary_name is not None:
            require_text(self.boundary_name, "boundary_name")


@dataclass(frozen=True, slots=True)
class FrontendTokenBinding(WebContractRecord):
    contract_type = "frontend_token_binding"
    semantic_token_ref: str
    implementation_name: str
    primitive_token_ref: str
    artifact_ref: str

    def __post_init__(self) -> None:
        for name in (
            "semantic_token_ref",
            "implementation_name",
            "primitive_token_ref",
            "artifact_ref",
        ):
            require_text(getattr(self, name), name)


@dataclass(frozen=True, slots=True)
class FrontendDependencyDecision(WebContractRecord):
    contract_type = "frontend_dependency_decision"
    dependency: str
    exact_version: str
    approved: bool
    rationale: str

    def __post_init__(self) -> None:
        for name in ("dependency", "exact_version", "rationale"):
            require_text(getattr(self, name), name)
        if self.exact_version.casefold() == "latest" or any(c in self.exact_version for c in "*^~"):
            raise ValueError("Dependency version must be exact")


@dataclass(frozen=True, slots=True)
class FrontendFinding(WebContractRecord):
    contract_type = "frontend_finding"
    finding_id: str
    code: FrontendFindingCode
    message: str
    affected_refs: tuple[str, ...] = ()
    blocking: bool = True

    def __post_init__(self) -> None:
        require_text(self.finding_id, "finding_id")
        require_text(self.message, "message")
        object.__setattr__(
            self, "affected_refs", freeze_strings(self.affected_refs, "affected_refs", sort=True)
        )


@dataclass(frozen=True, slots=True)
class FrontendEngineeringCheck(WebContractRecord):
    contract_type = "frontend_engineering_check"
    check_id: str
    kind: str
    adapter_identity: str
    tool_version: str
    source_tree_fingerprint: str
    status: FrontendCheckStatus
    exit_status: int | None
    diagnostic_digest: str
    evidence_refs: tuple[str, ...] = ()
    unit_refs: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for name in (
            "check_id",
            "kind",
            "adapter_identity",
            "tool_version",
            "source_tree_fingerprint",
            "diagnostic_digest",
        ):
            require_text(getattr(self, name), name)
        for name in ("evidence_refs", "unit_refs"):
            object.__setattr__(self, name, freeze_strings(getattr(self, name), name, sort=True))
        if self.status is FrontendCheckStatus.PASS and self.exit_status not in (None, 0):
            raise ValueError("Passing check cannot have failing exit status")


@dataclass(frozen=True, slots=True)
class FrontendImplementationProposal(WebContractRecord):
    contract_type = "frontend_implementation_proposal"
    contract_version: str
    proposal_id: str
    assignment_fingerprint: str
    unit_refs: tuple[str, ...]
    artifacts: tuple[FrontendArtifact, ...]
    surface_bindings: tuple[FrontendSurfaceBinding, ...]
    route_bindings: tuple[FrontendRouteBinding, ...]
    component_bindings: tuple[FrontendComponentBinding, ...]
    data_bindings: tuple[FrontendDataBinding, ...]
    token_bindings: tuple[FrontendTokenBinding, ...]
    dependency_decisions: tuple[FrontendDependencyDecision, ...]
    assumptions: tuple[str, ...]
    findings: tuple[FrontendFinding, ...]
    executor_identity: str
    executor_version: str

    def __post_init__(self) -> None:
        require_supported_version(self.contract_version)
        for name in (
            "proposal_id",
            "assignment_fingerprint",
            "executor_identity",
            "executor_version",
        ):
            require_text(getattr(self, name), name)
        object.__setattr__(
            self, "unit_refs", freeze_strings(self.unit_refs, "unit_refs", sort=True)
        )
        object.__setattr__(
            self, "assumptions", freeze_strings(self.assumptions, "assumptions", sort=True)
        )
        for name, key in (
            ("artifacts", lambda x: x.artifact_id),
            ("surface_bindings", lambda x: x.surface_ref),
            ("route_bindings", lambda x: x.route_ref),
            ("component_bindings", lambda x: x.component_ref),
            ("data_bindings", lambda x: x.binding_id),
            ("token_bindings", lambda x: x.semantic_token_ref),
            ("dependency_decisions", lambda x: x.dependency),
            ("findings", lambda x: x.finding_id),
        ):
            object.__setattr__(self, name, _sorted_unique_records(getattr(self, name), key, name))


@dataclass(frozen=True, slots=True)
class FrontendUnitResult(WebContractRecord):
    contract_type = "frontend_unit_result"
    unit_ref: str
    completed: bool
    artifact_refs: tuple[str, ...]
    finding_refs: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        require_text(self.unit_ref, "unit_ref")
        for name in ("artifact_refs", "finding_refs"):
            object.__setattr__(self, name, freeze_strings(getattr(self, name), name, sort=True))


@dataclass(frozen=True, slots=True)
class FrontendCompletionPackage(WebContractRecord):
    contract_type = "frontend_completion_package"
    contract_version: str
    completion_id: str
    project_id: str
    runtime_state: WebLifecycleStatus
    authorization_ref: ContractRef
    implementation_plan_fingerprint: str
    proposal_fingerprint: str
    change_set_fingerprint: str
    receipt: WorkspaceExecutionReceipt
    pre_tree_fingerprint: str
    post_tree_fingerprint: str
    adapter_identity: str
    unit_results: tuple[FrontendUnitResult, ...]
    engineering_checks: tuple[FrontendEngineeringCheck, ...]
    findings: tuple[FrontendFinding, ...]
    reconciliation_status: ReconciliationStatus
    w07_handoff: tuple[str, ...]
    readiness: FrontendReadiness

    def __post_init__(self) -> None:
        require_supported_version(self.contract_version)
        for name in (
            "completion_id",
            "project_id",
            "implementation_plan_fingerprint",
            "proposal_fingerprint",
            "change_set_fingerprint",
            "pre_tree_fingerprint",
            "post_tree_fingerprint",
            "adapter_identity",
        ):
            require_text(getattr(self, name), name)
        if self.runtime_state is not WebLifecycleStatus.IMPLEMENTING:
            raise ValueError("Frontend completion must remain IMPLEMENTING")
        object.__setattr__(
            self,
            "unit_results",
            _sorted_unique_records(self.unit_results, lambda x: x.unit_ref, "unit_results"),
        )
        object.__setattr__(
            self,
            "engineering_checks",
            _sorted_unique_records(
                self.engineering_checks, lambda x: x.check_id, "engineering_checks"
            ),
        )
        object.__setattr__(
            self,
            "findings",
            _sorted_unique_records(self.findings, lambda x: x.finding_id, "findings"),
        )
        object.__setattr__(
            self, "w07_handoff", freeze_strings(self.w07_handoff, "w07_handoff", sort=True)
        )
        blocked = (
            any(item.blocking for item in self.findings)
            or any(
                item.status in {FrontendCheckStatus.FAIL, FrontendCheckStatus.INCONCLUSIVE}
                for item in self.engineering_checks
            )
            or not all(item.completed for item in self.unit_results)
            or self.reconciliation_status is ReconciliationStatus.REQUIRED
        )
        if blocked != (self.readiness is FrontendReadiness.BLOCKED):
            raise ValueError("Frontend readiness contradicts completion evidence")


@dataclass(frozen=True, slots=True)
class FrontendReviewPackage(WebContractRecord):
    contract_type = "frontend_review_package"
    contract_version: str
    review_id: str
    project_id: str
    completion_ref: ContractRef
    findings: tuple[FrontendFinding, ...]
    readiness: FrontendReadiness

    def __post_init__(self) -> None:
        require_supported_version(self.contract_version)
        require_text(self.review_id, "review_id")
        require_text(self.project_id, "project_id")
        object.__setattr__(
            self,
            "findings",
            _sorted_unique_records(self.findings, lambda x: x.finding_id, "findings"),
        )


__all__ = tuple(name for name in globals() if name.startswith("Frontend"))
