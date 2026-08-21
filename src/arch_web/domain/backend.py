"""Immutable W07 backend, application-data, and integration contracts."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum, unique

from arch_web.contracts.versions import require_supported_version
from arch_web.domain._base import WebContractRecord, freeze_strings, require_text
from arch_web.domain.enums import WebLifecycleStatus
from arch_web.domain.frontend import FrontendCheckStatus
from arch_web.domain.references import ContractRef
from arch_web.domain.workspace import ReconciliationStatus, WorkspaceExecutionReceipt


def _records[T](values: tuple[T, ...], key: Callable[[T], str], label: str) -> tuple[T, ...]:
    ordered = tuple(sorted(values, key=key))
    keys = tuple(key(item) for item in ordered)
    if len(keys) != len(set(keys)):
        raise ValueError(f"{label} must be unique")
    return ordered


@unique
class BackendDisposition(StrEnum):
    NOT_APPLICABLE = "not_applicable"
    COMPLETE_FOR_REVIEW = "complete_for_review"
    BLOCKED = "blocked"


@unique
class BindingClosureStatus(StrEnum):
    IMPLEMENTED = "implemented"
    NOT_APPLICABLE = "not_applicable"
    DEFERRED_WITH_AUTHORITY = "deferred_with_authority"
    BLOCKED = "blocked"


@unique
class DataSensitivity(StrEnum):
    PUBLIC = "public"
    INTERNAL = "internal"
    PERSONAL = "personal"
    SENSITIVE = "sensitive"


@unique
class DataSourceKind(StrEnum):
    USER_GENERATED = "user_generated"
    SYSTEM_DERIVED = "system_derived"
    EXTERNAL = "external"


@unique
class FailureKind(StrEnum):
    VALIDATION = "validation"
    UNAUTHENTICATED = "unauthenticated"
    UNAUTHORIZED = "unauthorized"
    NOT_FOUND = "not_found"
    CONFLICT = "conflict"
    PRECONDITION_FAILED = "precondition_failed"
    RATE_LIMITED = "rate_limited"
    DEPENDENCY_UNAVAILABLE = "dependency_unavailable"
    TIMEOUT = "timeout"
    PERSISTENCE_UNAVAILABLE = "persistence_unavailable"
    INTERNAL = "internal"


@unique
class BackendArtifactKind(StrEnum):
    SOURCE = "source"
    TEST = "test"
    MIGRATION = "migration"
    SCHEMA = "schema"
    CONFIG_EXAMPLE = "config_example"


@unique
class BackendFindingCode(StrEnum):
    WRONG_LIFECYCLE = "wrong_lifecycle"
    STALE_EVIDENCE = "stale_evidence"
    UNAUTHORIZED_UNIT = "unauthorized_unit"
    PATH_CLAIM_VIOLATION = "path_claim_violation"
    FRONTEND_BACKEND_MISMATCH = "frontend_backend_mismatch"
    INVENTED_SEMANTICS = "invented_semantics"
    UNCLOSED_BINDING = "unclosed_binding"
    RUNTIME_PERSISTENCE_COUPLING = "runtime_persistence_coupling"
    UNRESOLVED_DATASTORE = "unresolved_datastore"
    MIGRATION_CONFLICT = "migration_conflict"
    DESTRUCTIVE_MIGRATION = "destructive_migration"
    MISSING_VALIDATION = "missing_validation"
    MISSING_AUTHORIZATION = "missing_authorization"
    UI_ONLY_AUTHORIZATION = "ui_only_authorization"
    SECRET_EXPOSURE = "secret_exposure"
    INJECTION_RISK = "injection_risk"
    UNSAFE_INTEGRATION = "unsafe_integration"
    MISSING_WEBHOOK_VERIFICATION = "missing_webhook_verification"
    MISSING_IDEMPOTENCY = "missing_idempotency"
    SENSITIVE_LOGGING = "sensitive_logging"
    HIDDEN_NETWORK = "hidden_network"
    TRANSACTION_DEFECT = "transaction_defect"
    CHECK_FAILED = "check_failed"
    MISSING_CHECK = "missing_check"
    RECONCILIATION_REQUIRED = "reconciliation_required"
    SCOPE_LEAKAGE = "scope_leakage"
    UNSUPPORTED_BACKEND_STACK = "unsupported_backend_stack"


@dataclass(frozen=True, slots=True)
class DataFieldSpec(WebContractRecord):
    contract_type = "data_field_spec"
    field_id: str
    data_type: str
    required: bool
    nullable: bool
    unique: bool
    client_writable: bool
    sensitivity: DataSensitivity
    purpose: str

    def __post_init__(self) -> None:
        for name in ("field_id", "data_type", "purpose"):
            require_text(getattr(self, name), name)
        if self.required and self.nullable:
            raise ValueError("A required field cannot be nullable")


@dataclass(frozen=True, slots=True)
class DataOwnershipPolicy(WebContractRecord):
    contract_type = "data_ownership_policy"
    owner_domain: str
    source_kind: DataSourceKind
    access_policy: str
    export_policy: str
    logging_restrictions: tuple[str, ...]

    def __post_init__(self) -> None:
        for name in ("owner_domain", "access_policy", "export_policy"):
            require_text(getattr(self, name), name)
        object.__setattr__(
            self,
            "logging_restrictions",
            freeze_strings(self.logging_restrictions, "logging_restrictions", sort=True),
        )


@dataclass(frozen=True, slots=True)
class DataLifecyclePolicy(WebContractRecord):
    contract_type = "data_lifecycle_policy"
    retention_policy: str
    deletion_policy: str
    anonymization_policy: str | None
    auditability: str

    def __post_init__(self) -> None:
        for name in ("retention_policy", "deletion_policy", "auditability"):
            require_text(getattr(self, name), name)
        if self.retention_policy.casefold() in {"forever", "indefinite", "unlimited"}:
            raise ValueError("Indefinite retention requires explicit external authority")
        if self.anonymization_policy is not None:
            require_text(self.anonymization_policy, "anonymization_policy")


@dataclass(frozen=True, slots=True)
class DataEntitySpec(WebContractRecord):
    contract_type = "data_entity_spec"
    entity_id: str
    purpose: str
    identity_field_ref: str
    fields: tuple[DataFieldSpec, ...]
    ownership: DataOwnershipPolicy
    lifecycle: DataLifecyclePolicy
    requirement_refs: tuple[str, ...]
    interface_refs: tuple[str, ...]

    def __post_init__(self) -> None:
        for name in ("entity_id", "purpose", "identity_field_ref"):
            require_text(getattr(self, name), name)
        object.__setattr__(
            self, "fields", _records(self.fields, lambda item: item.field_id, "fields")
        )
        if self.identity_field_ref not in {item.field_id for item in self.fields}:
            raise ValueError("Entity identity field is missing")
        for name in ("requirement_refs", "interface_refs"):
            object.__setattr__(self, name, freeze_strings(getattr(self, name), name, sort=True))


@dataclass(frozen=True, slots=True)
class ApplicationDataContract(WebContractRecord):
    contract_type = "application_data_contract"
    contract_version: str
    contract_id: str
    project_id: str
    entities: tuple[DataEntitySpec, ...]

    def __post_init__(self) -> None:
        require_supported_version(self.contract_version)
        require_text(self.contract_id, "contract_id")
        require_text(self.project_id, "project_id")
        object.__setattr__(
            self, "entities", _records(self.entities, lambda item: item.entity_id, "entities")
        )


@dataclass(frozen=True, slots=True)
class FailurePolicy(WebContractRecord):
    contract_type = "failure_policy"
    failure: FailureKind
    public_code: str
    frontend_state: str
    retryable: bool
    expose_internal_detail: bool = False

    def __post_init__(self) -> None:
        require_text(self.public_code, "public_code")
        require_text(self.frontend_state, "frontend_state")
        if self.expose_internal_detail:
            raise ValueError("Public failures cannot expose internal detail")


@dataclass(frozen=True, slots=True)
class BackendOperationContract(WebContractRecord):
    contract_type = "backend_operation_contract"
    operation_id: str
    purpose: str
    input_field_refs: tuple[str, ...]
    output_field_refs: tuple[str, ...]
    failure_kinds: tuple[FailureKind, ...]
    authentication_required: bool
    authorization_rule_ref: str | None
    idempotency_required: bool
    idempotency_scope: str | None
    sensitivity: DataSensitivity
    requirement_refs: tuple[str, ...]
    architecture_refs: tuple[str, ...]
    frontend_binding_refs: tuple[str, ...]

    def __post_init__(self) -> None:
        require_text(self.operation_id, "operation_id")
        require_text(self.purpose, "purpose")
        for name in (
            "input_field_refs",
            "output_field_refs",
            "requirement_refs",
            "architecture_refs",
            "frontend_binding_refs",
        ):
            object.__setattr__(self, name, freeze_strings(getattr(self, name), name, sort=True))
        object.__setattr__(
            self,
            "failure_kinds",
            tuple(sorted(set(self.failure_kinds), key=lambda item: item.value)),
        )
        if self.authentication_required and self.authorization_rule_ref is None:
            raise ValueError("Authenticated operation requires server authorization")
        if self.authorization_rule_ref is not None:
            require_text(self.authorization_rule_ref, "authorization_rule_ref")
        if self.idempotency_required != (self.idempotency_scope is not None):
            raise ValueError("Idempotency requirement and scope must agree")


@dataclass(frozen=True, slots=True)
class BackendInterfaceContract(WebContractRecord):
    contract_type = "backend_interface_contract"
    contract_version: str
    interface_id: str
    project_id: str
    transport: str
    operations: tuple[BackendOperationContract, ...]
    failure_policies: tuple[FailurePolicy, ...]

    def __post_init__(self) -> None:
        require_supported_version(self.contract_version)
        for name in ("interface_id", "project_id", "transport"):
            require_text(getattr(self, name), name)
        object.__setattr__(
            self,
            "operations",
            _records(self.operations, lambda item: item.operation_id, "operations"),
        )
        object.__setattr__(
            self,
            "failure_policies",
            _records(self.failure_policies, lambda item: item.failure.value, "failure_policies"),
        )


@dataclass(frozen=True, slots=True)
class BackendDataBinding(WebContractRecord):
    contract_type = "backend_data_binding"
    frontend_binding_ref: str
    operation_ref: str | None
    status: BindingClosureStatus
    authority_ref: str | None = None

    def __post_init__(self) -> None:
        require_text(self.frontend_binding_ref, "frontend_binding_ref")
        if self.operation_ref is not None:
            require_text(self.operation_ref, "operation_ref")
        if self.status is BindingClosureStatus.IMPLEMENTED and self.operation_ref is None:
            raise ValueError("Implemented binding requires an operation")
        if (
            self.status is BindingClosureStatus.DEFERRED_WITH_AUTHORITY
            and self.authority_ref is None
        ):
            raise ValueError("Deferred binding requires authority")


@dataclass(frozen=True, slots=True)
class AuthenticationContract(WebContractRecord):
    contract_type = "authentication_contract"
    contract_version: str
    contract_id: str
    model: str
    provider: str
    identity_source: str
    secret_refs: tuple[str, ...]
    client_identity_trusted: bool = False

    def __post_init__(self) -> None:
        require_supported_version(self.contract_version)
        for name in ("contract_id", "model", "provider", "identity_source"):
            require_text(getattr(self, name), name)
        object.__setattr__(
            self, "secret_refs", freeze_strings(self.secret_refs, "secret_refs", sort=True)
        )
        if self.client_identity_trusted:
            raise ValueError("Authenticated identity cannot trust arbitrary client identity")


@dataclass(frozen=True, slots=True)
class AuthorizationRule(WebContractRecord):
    contract_type = "authorization_rule"
    rule_id: str
    subject: str
    action: str
    resource: str
    ownership_condition: str | None
    default_deny: bool
    requirement_refs: tuple[str, ...]

    def __post_init__(self) -> None:
        for name in ("rule_id", "subject", "action", "resource"):
            require_text(getattr(self, name), name)
        if self.ownership_condition is not None:
            require_text(self.ownership_condition, "ownership_condition")
        object.__setattr__(
            self,
            "requirement_refs",
            freeze_strings(self.requirement_refs, "requirement_refs", sort=True),
        )


@dataclass(frozen=True, slots=True)
class PersistenceContract(WebContractRecord):
    contract_type = "persistence_contract"
    contract_version: str
    contract_id: str
    technology: str
    application_store_ref: str
    runtime_store_ref: str
    repository_refs: tuple[str, ...]
    transaction_policy: str
    isolation_policy: str
    configuration_secret_ref: str | None

    def __post_init__(self) -> None:
        require_supported_version(self.contract_version)
        for name in (
            "contract_id",
            "technology",
            "application_store_ref",
            "runtime_store_ref",
            "transaction_policy",
            "isolation_policy",
        ):
            require_text(getattr(self, name), name)
        object.__setattr__(
            self,
            "repository_refs",
            freeze_strings(self.repository_refs, "repository_refs", sort=True),
        )
        if self.application_store_ref.casefold() == self.runtime_store_ref.casefold():
            raise ValueError("Application persistence must be separate from Runtime persistence")
        if self.configuration_secret_ref is not None:
            require_text(self.configuration_secret_ref, "configuration_secret_ref")


@dataclass(frozen=True, slots=True)
class ApplicationMigrationStep(WebContractRecord):
    contract_type = "application_migration_step"
    migration_id: str
    predecessor: str | None
    target_version: str
    checksum: str
    statement: str
    destructive: bool
    rollback_policy: str
    postconditions: tuple[str, ...]

    def __post_init__(self) -> None:
        for name in ("migration_id", "target_version", "checksum", "statement", "rollback_policy"):
            require_text(getattr(self, name), name)
        if self.predecessor is not None:
            require_text(self.predecessor, "predecessor")
        object.__setattr__(
            self, "postconditions", freeze_strings(self.postconditions, "postconditions", sort=True)
        )


@dataclass(frozen=True, slots=True)
class ApplicationMigrationPlan(WebContractRecord):
    contract_type = "application_migration_plan"
    contract_version: str
    plan_id: str
    application_store_ref: str
    steps: tuple[ApplicationMigrationStep, ...]
    destructive_authority_ref: str | None = None

    def __post_init__(self) -> None:
        require_supported_version(self.contract_version)
        require_text(self.plan_id, "plan_id")
        require_text(self.application_store_ref, "application_store_ref")
        steps = _records(self.steps, lambda item: item.migration_id, "migration steps")
        by_id = {item.migration_id: item for item in steps}
        roots = [item for item in steps if item.predecessor is None]
        if steps and len(roots) != 1:
            raise ValueError("Migration plan requires one root")
        for step in steps:
            if step.predecessor is not None and step.predecessor not in by_id:
                raise ValueError("Migration predecessor is missing")
        if any(item.destructive for item in steps) and self.destructive_authority_ref is None:
            raise ValueError("Destructive migration requires explicit authority")
        object.__setattr__(self, "steps", steps)


@dataclass(frozen=True, slots=True)
class ExternalIntegrationContract(WebContractRecord):
    contract_type = "external_integration_contract"
    integration_id: str
    provider: str
    direction: str
    purpose: str
    secret_ref: str | None
    timeout_seconds: int
    retry_policy: str
    idempotency_required: bool
    webhook_signature_required: bool
    pii_policy: str
    logging_policy: str

    def __post_init__(self) -> None:
        for name in (
            "integration_id",
            "provider",
            "direction",
            "purpose",
            "retry_policy",
            "pii_policy",
            "logging_policy",
        ):
            require_text(getattr(self, name), name)
        if self.secret_ref is not None:
            require_text(self.secret_ref, "secret_ref")
        if self.timeout_seconds < 1:
            raise ValueError("Integration timeout must be positive")
        if self.direction == "inbound_webhook" and not self.webhook_signature_required:
            raise ValueError("Inbound webhooks require signature verification")


@dataclass(frozen=True, slots=True)
class BackendArtifact(WebContractRecord):
    contract_type = "backend_artifact"
    artifact_id: str
    unit_ref: str
    claim_ref: str
    path: str
    kind: BackendArtifactKind
    content: str
    content_fingerprint: str

    def __post_init__(self) -> None:
        for name in ("artifact_id", "unit_ref", "claim_ref", "path", "content_fingerprint"):
            require_text(getattr(self, name), name)
        if not self.content:
            raise ValueError("Backend artifact content must not be empty")


@dataclass(frozen=True, slots=True)
class BackendAssignmentPacket(WebContractRecord):
    contract_type = "backend_assignment_packet"
    contract_version: str
    assignment_id: str
    project_id: str
    runtime_state: WebLifecycleStatus
    runtime_record_version: int
    runtime_record_fingerprint: str
    requirements_fingerprint: str
    architecture_fingerprint: str
    implementation_plan_fingerprint: str
    frontend_completion_fingerprint: str
    frontend_proposal_fingerprint: str
    stack_fingerprint: str
    managed_tree_fingerprint: str
    git_head: str | None
    selected_unit_refs: tuple[str, ...]
    path_claim_refs: tuple[str, ...]
    pending_frontend_bindings: tuple[str, ...]
    approved_contract_fingerprints: tuple[str, ...]
    prohibited_scope: tuple[str, ...]

    def __post_init__(self) -> None:
        require_supported_version(self.contract_version)
        for name in (
            "assignment_id",
            "project_id",
            "runtime_record_fingerprint",
            "requirements_fingerprint",
            "architecture_fingerprint",
            "implementation_plan_fingerprint",
            "frontend_completion_fingerprint",
            "frontend_proposal_fingerprint",
            "stack_fingerprint",
            "managed_tree_fingerprint",
        ):
            require_text(getattr(self, name), name)
        if self.runtime_state is not WebLifecycleStatus.IMPLEMENTING:
            raise ValueError("Backend assignment requires IMPLEMENTING")
        if self.runtime_record_version < 1:
            raise ValueError("runtime_record_version must be positive")
        if self.git_head is not None:
            require_text(self.git_head, "git_head")
        for name in (
            "selected_unit_refs",
            "path_claim_refs",
            "pending_frontend_bindings",
            "approved_contract_fingerprints",
            "prohibited_scope",
        ):
            object.__setattr__(self, name, freeze_strings(getattr(self, name), name, sort=True))


@dataclass(frozen=True, slots=True)
class BackendFinding(WebContractRecord):
    contract_type = "backend_finding"
    finding_id: str
    code: BackendFindingCode
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
class BackendEngineeringCheck(WebContractRecord):
    contract_type = "backend_engineering_check"
    check_id: str
    kind: str
    adapter_identity: str
    tool_version: str
    source_tree_fingerprint: str
    status: FrontendCheckStatus
    exit_status: int | None
    diagnostic_digest: str
    evidence_refs: tuple[str, ...] = ()

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
        object.__setattr__(
            self, "evidence_refs", freeze_strings(self.evidence_refs, "evidence_refs", sort=True)
        )
        if self.status is FrontendCheckStatus.PASS and self.exit_status not in {None, 0}:
            raise ValueError("Passing check cannot have failing exit status")


@dataclass(frozen=True, slots=True)
class BackendImplementationProposal(WebContractRecord):
    contract_type = "backend_implementation_proposal"
    contract_version: str
    proposal_id: str
    assignment_fingerprint: str
    unit_refs: tuple[str, ...]
    artifacts: tuple[BackendArtifact, ...]
    bindings: tuple[BackendDataBinding, ...]
    interface: BackendInterfaceContract
    data_contract: ApplicationDataContract
    authentication: AuthenticationContract
    authorization_rules: tuple[AuthorizationRule, ...]
    persistence: PersistenceContract
    migrations: ApplicationMigrationPlan
    integrations: tuple[ExternalIntegrationContract, ...]
    assumptions: tuple[str, ...]
    findings: tuple[BackendFinding, ...]
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
            self, "artifacts", _records(self.artifacts, lambda item: item.artifact_id, "artifacts")
        )
        object.__setattr__(
            self,
            "bindings",
            _records(self.bindings, lambda item: item.frontend_binding_ref, "bindings"),
        )
        object.__setattr__(
            self,
            "authorization_rules",
            _records(self.authorization_rules, lambda item: item.rule_id, "authorization_rules"),
        )
        object.__setattr__(
            self,
            "integrations",
            _records(self.integrations, lambda item: item.integration_id, "integrations"),
        )
        object.__setattr__(
            self, "assumptions", freeze_strings(self.assumptions, "assumptions", sort=True)
        )
        object.__setattr__(
            self, "findings", _records(self.findings, lambda item: item.finding_id, "findings")
        )


@dataclass(frozen=True, slots=True)
class BackendUnitResult(WebContractRecord):
    contract_type = "backend_unit_result"
    unit_ref: str
    completed: bool
    artifact_refs: tuple[str, ...]

    def __post_init__(self) -> None:
        require_text(self.unit_ref, "unit_ref")
        object.__setattr__(
            self, "artifact_refs", freeze_strings(self.artifact_refs, "artifact_refs", sort=True)
        )


@dataclass(frozen=True, slots=True)
class BackendCompletionPackage(WebContractRecord):
    contract_type = "backend_completion_package"
    contract_version: str
    completion_id: str
    project_id: str
    runtime_state: WebLifecycleStatus
    disposition: BackendDisposition
    assignment_fingerprint: str
    proposal_fingerprint: str | None
    frontend_completion_ref: ContractRef
    binding_closures: tuple[BackendDataBinding, ...]
    unit_results: tuple[BackendUnitResult, ...]
    interface_fingerprint: str | None
    data_contract_fingerprint: str | None
    persistence_fingerprint: str | None
    migration_plan_fingerprint: str | None
    workspace_receipt: WorkspaceExecutionReceipt | None
    pre_tree_fingerprint: str
    post_tree_fingerprint: str
    engineering_checks: tuple[BackendEngineeringCheck, ...]
    findings: tuple[BackendFinding, ...]
    reconciliation_status: ReconciliationStatus
    w08_handoff: tuple[str, ...]

    def __post_init__(self) -> None:
        require_supported_version(self.contract_version)
        for name in (
            "completion_id",
            "project_id",
            "assignment_fingerprint",
            "pre_tree_fingerprint",
            "post_tree_fingerprint",
        ):
            require_text(getattr(self, name), name)
        if self.runtime_state is not WebLifecycleStatus.IMPLEMENTING:
            raise ValueError("Backend completion must remain IMPLEMENTING")
        for name in (
            "proposal_fingerprint",
            "interface_fingerprint",
            "data_contract_fingerprint",
            "persistence_fingerprint",
            "migration_plan_fingerprint",
        ):
            value = getattr(self, name)
            if value is not None:
                require_text(value, name)
        object.__setattr__(
            self,
            "binding_closures",
            _records(
                self.binding_closures, lambda item: item.frontend_binding_ref, "binding_closures"
            ),
        )
        object.__setattr__(
            self,
            "unit_results",
            _records(self.unit_results, lambda item: item.unit_ref, "unit_results"),
        )
        object.__setattr__(
            self,
            "engineering_checks",
            _records(self.engineering_checks, lambda item: item.check_id, "engineering_checks"),
        )
        object.__setattr__(
            self, "findings", _records(self.findings, lambda item: item.finding_id, "findings")
        )
        object.__setattr__(
            self, "w08_handoff", freeze_strings(self.w08_handoff, "w08_handoff", sort=True)
        )
        blocked = (
            any(item.blocking for item in self.findings)
            or any(
                item.status in {FrontendCheckStatus.FAIL, FrontendCheckStatus.INCONCLUSIVE}
                for item in self.engineering_checks
            )
            or any(item.status is BindingClosureStatus.BLOCKED for item in self.binding_closures)
            or not all(item.completed for item in self.unit_results)
            or self.reconciliation_status is ReconciliationStatus.REQUIRED
        )
        if self.disposition is BackendDisposition.NOT_APPLICABLE:
            if (
                self.binding_closures
                or self.unit_results
                or self.proposal_fingerprint is not None
                or self.workspace_receipt is not None
            ):
                raise ValueError("NOT_APPLICABLE cannot contain backend work")
        elif blocked != (self.disposition is BackendDisposition.BLOCKED):
            raise ValueError("Backend disposition contradicts completion evidence")


@dataclass(frozen=True, slots=True)
class BackendReviewPackage(WebContractRecord):
    contract_type = "backend_review_package"
    contract_version: str
    review_id: str
    project_id: str
    completion_ref: ContractRef
    findings: tuple[BackendFinding, ...]
    disposition: BackendDisposition

    def __post_init__(self) -> None:
        require_supported_version(self.contract_version)
        require_text(self.review_id, "review_id")
        require_text(self.project_id, "project_id")
        object.__setattr__(
            self, "findings", _records(self.findings, lambda item: item.finding_id, "findings")
        )


__all__ = tuple(
    name
    for name in globals()
    if name.startswith(
        (
            "Application",
            "Authentication",
            "Authorization",
            "Backend",
            "Binding",
            "Data",
            "External",
            "Failure",
            "Persistence",
        )
    )
)
