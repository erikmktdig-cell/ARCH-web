"""Immutable W05 workspace, planning, execution, and review contracts."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum, unique

from arch_web.contracts.versions import require_supported_version
from arch_web.domain._base import WebContractRecord, freeze_strings, require_text
from arch_web.domain.enums import WebRoute
from arch_web.domain.references import ContractRef, EvidenceRef


@unique
class WorkspaceKind(StrEnum):
    NEW_REPOSITORY = "new_repository"
    EXISTING_REPOSITORY = "existing_repository"


@unique
class ImplementationUnitKind(StrEnum):
    FRONTEND = "frontend"
    BACKEND = "backend"
    SHARED = "shared"
    CONFIGURATION = "configuration"
    TESTING_SUPPORT = "testing_support"


@unique
class PathClaimMode(StrEnum):
    EXCLUSIVE = "exclusive"
    SERIALIZED_SHARED = "serialized_shared"


@unique
class WorkspaceOperation(StrEnum):
    CREATE_DIRECTORY = "create_directory"
    CREATE_FILE = "create_file"
    UPDATE_FILE = "update_file"
    DELETE_FILE = "delete_file"
    GIT_INIT = "git_init"
    GIT_COMMIT = "git_commit"


@unique
class ExecutionOutcome(StrEnum):
    NOT_APPLIED = "not_applied"
    APPLIED = "applied"
    NOOP_ALREADY_SATISFIED = "noop_already_satisfied"
    FAILED_ROLLED_BACK = "failed_rolled_back"
    RECONCILIATION_REQUIRED = "reconciliation_required"


@unique
class ReconciliationStatus(StrEnum):
    CLEAN = "clean"
    REQUIRED = "required"


@unique
class WorkspaceFindingCode(StrEnum):
    UPSTREAM_MISMATCH = "upstream_mismatch"
    PATH_ESCAPE = "path_escape"
    GIT_METADATA_MUTATION = "git_metadata_mutation"
    DIRTY_REPOSITORY = "dirty_repository"
    DETACHED_HEAD = "detached_head"
    UNMANAGED_OVERWRITE = "unmanaged_overwrite"
    STALE_BASELINE = "stale_baseline"
    PATH_CLAIM_CONFLICT = "path_claim_conflict"
    UNRESOLVED_STACK = "unresolved_stack"
    MISSING_TOOL = "missing_tool"
    SECRET_ARTIFACT = "secret_artifact"
    REQUIRED_LOCKFILE_ABSENT = "required_lockfile_absent"
    POST_STATE_MISMATCH = "post_state_mismatch"
    RECONCILIATION_REQUIRED = "reconciliation_required"
    MISSING_IMPLEMENTATION_DISPOSITION = "missing_implementation_disposition"
    PRODUCT_IMPLEMENTATION_LEAK = "product_implementation_leak"


@unique
class WorkspaceReadiness(StrEnum):
    NOT_READY = "not_ready"
    READY_FOR_REVIEW = "ready_for_review"
    APPROVED = "approved"


@dataclass(frozen=True, slots=True)
class WorkspaceTarget(WebContractRecord):
    contract_type = "workspace_target"

    workspace_id: str
    project_id: str
    root_path: str
    kind: WorkspaceKind
    route: WebRoute
    case_sensitive: bool = False

    def __post_init__(self) -> None:
        for name in ("workspace_id", "project_id", "root_path"):
            require_text(getattr(self, name), name)


@dataclass(frozen=True, slots=True)
class FileEvidence(WebContractRecord):
    contract_type = "file_evidence"

    path: str
    fingerprint: str
    size: int

    def __post_init__(self) -> None:
        require_text(self.path, "path")
        require_text(self.fingerprint, "fingerprint")
        if self.size < 0:
            raise ValueError("size cannot be negative")


@dataclass(frozen=True, slots=True)
class RepositoryBaseline(WebContractRecord):
    contract_type = "repository_baseline"

    present: bool
    head: str | None
    branch: str | None
    detached: bool
    dirty_paths: tuple[str, ...] = ()
    remotes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for name in ("head", "branch"):
            value = getattr(self, name)
            if value is not None:
                require_text(value, name)
        object.__setattr__(
            self, "dirty_paths", freeze_strings(self.dirty_paths, "dirty_paths", sort=True)
        )
        object.__setattr__(self, "remotes", freeze_strings(self.remotes, "remotes", sort=True))


@dataclass(frozen=True, slots=True)
class WorkspaceBaseline(WebContractRecord):
    contract_type = "workspace_baseline"

    workspace_id: str
    project_id: str
    exists: bool
    files: tuple[FileEvidence, ...]
    tree_fingerprint: str
    repository: RepositoryBaseline
    toolchain_capabilities: tuple[ToolchainCapability, ...] = ()

    def __post_init__(self) -> None:
        require_text(self.workspace_id, "workspace_id")
        require_text(self.project_id, "project_id")
        require_text(self.tree_fingerprint, "tree_fingerprint")
        files = tuple(sorted(self.files, key=lambda item: item.path))
        keys = tuple(item.path.casefold() for item in files)
        if len(keys) != len(set(keys)):
            raise ValueError("Workspace contains a case-colliding path")
        object.__setattr__(self, "files", files)
        capabilities = tuple(sorted(self.toolchain_capabilities, key=lambda item: item.tool_id))
        if len({item.tool_id for item in capabilities}) != len(capabilities):
            raise ValueError("Toolchain capability IDs must be unique")
        object.__setattr__(self, "toolchain_capabilities", capabilities)


@dataclass(frozen=True, slots=True)
class ToolchainCapability(WebContractRecord):
    contract_type = "toolchain_capability"

    tool_id: str
    executable: str
    available: bool
    version: str | None
    output_digest: str

    def __post_init__(self) -> None:
        for name in ("tool_id", "executable", "output_digest"):
            require_text(getattr(self, name), name)
        if self.version is not None:
            require_text(self.version, "version")


@dataclass(frozen=True, slots=True)
class ResolvedStackManifest(WebContractRecord):
    contract_type = "resolved_stack_manifest"

    contract_version: str
    manifest_id: str
    project_id: str
    source_profile_ref: ContractRef
    language: str
    runtime_requirement: str
    frontend_framework: str
    rendering_mode: str
    package_manager: str
    backend_model: str
    unit_test_runner: str
    e2e_test_runner: str
    lockfile_policy: str
    required_tools: tuple[str, ...]
    network_required: bool
    constraints: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        require_supported_version(self.contract_version)
        for name in (
            "manifest_id",
            "project_id",
            "language",
            "runtime_requirement",
            "frontend_framework",
            "rendering_mode",
            "package_manager",
            "backend_model",
            "unit_test_runner",
            "e2e_test_runner",
            "lockfile_policy",
        ):
            value = require_text(getattr(self, name), name)
            if value.casefold() == "latest":
                raise ValueError(f"{name} cannot use latest")
        object.__setattr__(
            self, "required_tools", freeze_strings(self.required_tools, "required_tools", sort=True)
        )
        object.__setattr__(
            self, "constraints", freeze_strings(self.constraints, "constraints", sort=True)
        )


@dataclass(frozen=True, slots=True)
class PathClaim(WebContractRecord):
    contract_type = "path_claim"

    claim_id: str
    unit_ref: str
    path_pattern: str
    mode: PathClaimMode

    def __post_init__(self) -> None:
        for name in ("claim_id", "unit_ref", "path_pattern"):
            require_text(getattr(self, name), name)


@dataclass(frozen=True, slots=True)
class ImplementationUnit(WebContractRecord):
    contract_type = "implementation_unit"

    unit_id: str
    kind: ImplementationUnitKind
    objective: str
    requirement_refs: tuple[str, ...]
    architecture_refs: tuple[str, ...]
    surface_refs: tuple[str, ...]
    component_refs: tuple[str, ...]
    expected_paths: tuple[str, ...]
    dependency_refs: tuple[str, ...]
    acceptance_evidence: tuple[str, ...]
    owner_role: str
    risk: str
    prohibited_scope: tuple[str, ...]

    def __post_init__(self) -> None:
        for name in ("unit_id", "objective", "owner_role", "risk"):
            require_text(getattr(self, name), name)
        for name in (
            "requirement_refs",
            "architecture_refs",
            "surface_refs",
            "component_refs",
            "expected_paths",
            "dependency_refs",
            "acceptance_evidence",
            "prohibited_scope",
        ):
            object.__setattr__(self, name, freeze_strings(getattr(self, name), name, sort=True))
        if not self.acceptance_evidence:
            raise ValueError("Implementation unit requires acceptance evidence")


@dataclass(frozen=True, slots=True)
class ImplementationPlan(WebContractRecord):
    contract_type = "implementation_plan"

    contract_version: str
    plan_id: str
    project_id: str
    requirements_ref: ContractRef
    architecture_ref: ContractRef
    design_system_ref: ContractRef
    ui_specification_ref: ContractRef
    ui_review_ref: ContractRef
    stack_ref: ContractRef
    units: tuple[ImplementationUnit, ...]
    path_claims: tuple[PathClaim, ...]

    def __post_init__(self) -> None:
        require_supported_version(self.contract_version)
        require_text(self.plan_id, "plan_id")
        require_text(self.project_id, "project_id")
        units = tuple(sorted(self.units, key=lambda item: item.unit_id))
        claims = tuple(sorted(self.path_claims, key=lambda item: item.claim_id))
        ids = {item.unit_id for item in units}
        if len(ids) != len(units):
            raise ValueError("Implementation unit IDs must be unique")
        for unit in units:
            if set(unit.dependency_refs) - ids or unit.unit_id in unit.dependency_refs:
                raise ValueError("Implementation unit dependency is invalid")
        _reject_dependency_cycles(units)
        if any(item.unit_ref not in ids for item in claims):
            raise ValueError("Path claim references missing unit")
        _reject_claim_conflicts(claims)
        object.__setattr__(self, "units", units)
        object.__setattr__(self, "path_claims", claims)


def _reject_dependency_cycles(units: tuple[ImplementationUnit, ...]) -> None:
    graph = {item.unit_id: item.dependency_refs for item in units}
    for start in graph:
        seen: set[str] = set()
        current = [start]
        while current:
            node = current.pop()
            if node in seen:
                raise ValueError("Implementation unit dependency cycle")
            seen.add(node)
            current.extend(graph[node])


def _claim_root(pattern: str) -> str:
    return pattern.removesuffix("/**").rstrip("/").casefold()


def _reject_claim_conflicts(claims: tuple[PathClaim, ...]) -> None:
    exclusive = tuple(item for item in claims if item.mode is PathClaimMode.EXCLUSIVE)
    for index, left in enumerate(exclusive):
        left_root = _claim_root(left.path_pattern)
        for right in exclusive[index + 1 :]:
            right_root = _claim_root(right.path_pattern)
            if (
                left_root == right_root
                or left_root.startswith(right_root + "/")
                or right_root.startswith(left_root + "/")
            ):
                raise ValueError("Exclusive path claims overlap")


@dataclass(frozen=True, slots=True)
class WorkspaceChange(WebContractRecord):
    contract_type = "workspace_change"

    change_id: str
    operation: WorkspaceOperation
    path: str | None
    new_fingerprint: str | None
    expected_old_fingerprint: str | None
    claim_ref: str | None
    unit_ref: str
    reason: str

    def __post_init__(self) -> None:
        require_text(self.change_id, "change_id")
        require_text(self.unit_ref, "unit_ref")
        require_text(self.reason, "reason")
        for name in ("path", "new_fingerprint", "expected_old_fingerprint", "claim_ref"):
            value = getattr(self, name)
            if value is not None:
                require_text(value, name)


@dataclass(frozen=True, slots=True)
class WorkspaceChangeSet(WebContractRecord):
    contract_type = "workspace_change_set"

    contract_version: str
    change_set_id: str
    project_id: str
    workspace_id: str
    implementation_plan_fingerprint: str
    baseline_fingerprint: str
    changes: tuple[WorkspaceChange, ...]

    def __post_init__(self) -> None:
        require_supported_version(self.contract_version)
        for name in (
            "change_set_id",
            "project_id",
            "workspace_id",
            "implementation_plan_fingerprint",
            "baseline_fingerprint",
        ):
            require_text(getattr(self, name), name)
        changes = tuple(sorted(self.changes, key=lambda item: item.change_id))
        if len({item.change_id for item in changes}) != len(changes):
            raise ValueError("Workspace change IDs must be unique")
        object.__setattr__(self, "changes", changes)


@dataclass(frozen=True, slots=True)
class WorkspaceExecutionPolicy(WebContractRecord):
    contract_type = "workspace_execution_policy"

    require_clean_repository: bool = True
    allow_detached_head: bool = False
    allow_delete: bool = False
    allow_network: bool = False
    create_local_commit: bool = False
    commit_message: str | None = None

    def __post_init__(self) -> None:
        if self.commit_message is not None:
            require_text(self.commit_message, "commit_message")
        if self.create_local_commit != (self.commit_message is not None):
            raise ValueError("Local commit policy requires exactly one commit message")


@dataclass(frozen=True, slots=True)
class WorkspaceDryRun(WebContractRecord):
    contract_type = "workspace_dry_run"

    change_set_fingerprint: str
    creates: tuple[str, ...]
    updates: tuple[str, ...]
    deletes: tuple[str, ...]
    git_actions: tuple[str, ...]
    policy_violations: tuple[str, ...]
    expected_post_fingerprint: str | None

    def __post_init__(self) -> None:
        require_text(self.change_set_fingerprint, "change_set_fingerprint")
        for name in ("creates", "updates", "deletes", "git_actions", "policy_violations"):
            object.__setattr__(self, name, freeze_strings(getattr(self, name), name, sort=True))
        if self.expected_post_fingerprint is not None:
            require_text(self.expected_post_fingerprint, "expected_post_fingerprint")


@dataclass(frozen=True, slots=True)
class RepositoryEvidence(WebContractRecord):
    contract_type = "repository_evidence"

    before_head: str | None
    after_head: str | None
    branch: str | None
    changed_paths: tuple[str, ...]
    clean_after: bool

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "changed_paths", freeze_strings(self.changed_paths, "changed_paths", sort=True)
        )


@dataclass(frozen=True, slots=True)
class WorkspaceExecutionReceipt(WebContractRecord):
    contract_type = "workspace_execution_receipt"

    contract_version: str
    execution_id: str
    project_id: str
    workspace_id: str
    change_set_fingerprint: str
    implementation_plan_fingerprint: str
    resolved_stack_fingerprint: str
    pre_baseline_fingerprint: str
    post_tree_fingerprint: str
    repository_evidence: RepositoryEvidence
    changed_paths: tuple[FileEvidence, ...]
    outcome: ExecutionOutcome
    reconciliation_status: ReconciliationStatus

    def __post_init__(self) -> None:
        require_supported_version(self.contract_version)
        for name in (
            "execution_id",
            "project_id",
            "workspace_id",
            "change_set_fingerprint",
            "implementation_plan_fingerprint",
            "resolved_stack_fingerprint",
            "pre_baseline_fingerprint",
            "post_tree_fingerprint",
        ):
            require_text(getattr(self, name), name)
        object.__setattr__(
            self, "changed_paths", tuple(sorted(self.changed_paths, key=lambda item: item.path))
        )
        if (
            self.outcome is ExecutionOutcome.RECONCILIATION_REQUIRED
            and self.reconciliation_status is not ReconciliationStatus.REQUIRED
        ):
            raise ValueError("Reconciliation outcome requires reconciliation status")


@dataclass(frozen=True, slots=True)
class WorkspaceFinding(WebContractRecord):
    contract_type = "workspace_finding"

    finding_id: str
    code: WorkspaceFindingCode
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
class WorkspaceReviewPackage(WebContractRecord):
    contract_type = "workspace_review_package"

    contract_version: str
    review_id: str
    project_id: str
    route: WebRoute
    plan_ref: ContractRef
    stack_ref: ContractRef
    change_set_ref: ContractRef
    receipt_ref: ContractRef | None
    findings: tuple[WorkspaceFinding, ...]
    readiness: WorkspaceReadiness
    approval_evidence_ref: EvidenceRef | None = None

    def __post_init__(self) -> None:
        require_supported_version(self.contract_version)
        require_text(self.review_id, "review_id")
        require_text(self.project_id, "project_id")
        object.__setattr__(
            self, "findings", tuple(sorted(self.findings, key=lambda item: item.finding_id))
        )
        if (
            any(item.blocking for item in self.findings)
            and self.readiness is not WorkspaceReadiness.NOT_READY
        ):
            raise ValueError("Blocking workspace findings require NOT_READY")
        if self.readiness is WorkspaceReadiness.APPROVED and self.approval_evidence_ref is None:
            raise ValueError("Approved workspace requires approval evidence")


__all__ = tuple(
    name
    for name in globals()
    if not name.startswith("_") and name not in {"annotations", "dataclass", "StrEnum", "unique"}
)
