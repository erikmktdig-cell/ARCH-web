"""Canonical Web lifecycle binding to public Kernel and Runtime workflow APIs."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from arch_kernel.contracts import (
    ChangeId,
    EffectType,
    EffectValueSource,
    ProjectId,
    SemanticVersion,
    TransitionDomain,
    TransitionEffect,
    TransitionId,
    TransitionTarget,
    WorkflowDefinition,
    WorkflowId,
    WorkflowNamespace,
    WorkflowStateKey,
    WorkflowTransitionDefinition,
)
from arch_kernel.kernel import (
    TransitionRegistry,
    WorkflowDefinitionRegistry,
    compute_content_fingerprint,
)
from arch_runtime import (
    ApplyTransitionCommand,
    InitializeWorkflowCommand,
    InitializeWorkflowResult,
    Runtime,
)

from arch_web.domain._base import WebContractRecord, require_text
from arch_web.domain.enums import WebLifecycleStatus

WEB_WORKFLOW_ID = WorkflowId.from_str("WFL-01HZX7M3FQ1T2Q9V8Y6K4C2B1A")
WEB_WORKFLOW_NAMESPACE = WorkflowNamespace.parse("arch_web.project_lifecycle")
WEB_WORKFLOW_DEFINITION_VERSION = SemanticVersion.parse("1.0.0")
_CONTRACT_VERSION = SemanticVersion.parse("1.0.0")
_DECLARED_AT = datetime(2026, 9, 2, tzinfo=UTC)


class WebWorkflowAuthorityError(RuntimeError):
    """Runtime does not contain the exact authoritative Web workflow evidence."""


@dataclass(frozen=True, slots=True)
class InitializeWebLifecycleCommand(WebContractRecord):
    """Explicitly initialize the canonical Web lifecycle on one Runtime project."""

    contract_type = "initialize_web_lifecycle_command"

    project_id: str
    idempotency_key: str
    expected_record_version: int
    expected_record_fingerprint: str
    expected_content_fingerprint: str
    actor_id: str
    actor_display_name: str | None = None

    def __post_init__(self) -> None:
        for name in (
            "project_id",
            "idempotency_key",
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
class WebLifecycleEvidence:
    """Verified read model of Runtime-owned Web lifecycle authority."""

    project_id: ProjectId
    workflow_id: WorkflowId
    workflow_namespace: WorkflowNamespace
    definition_version: SemanticVersion
    definition_fingerprint: str
    current_status: WebLifecycleStatus
    aggregate_record_version: int
    aggregate_record_fingerprint: str
    aggregate_content_fingerprint: str
    workflow_record_version: int
    workflow_content_fingerprint: str


def _web_workflow_definition() -> WorkflowDefinition:
    return WorkflowDefinition(
        contract_name="workflow_definition",
        contract_version=_CONTRACT_VERSION,
        schema_uri="urn:arch:contracts:workflow_definition:1.0.0",
        created_at=_DECLARED_AT,
        workflow_id=WEB_WORKFLOW_ID,
        namespace=WEB_WORKFLOW_NAMESPACE,
        definition_version=WEB_WORKFLOW_DEFINITION_VERSION,
        allowed_states=tuple(WorkflowStateKey.parse(item.value) for item in WebLifecycleStatus),
        initial_state=WorkflowStateKey.parse(WebLifecycleStatus.DRAFT.value),
    )


WEB_WORKFLOW_DEFINITION = _web_workflow_definition()
WEB_WORKFLOW_DEFINITION_REGISTRY = WorkflowDefinitionRegistry((WEB_WORKFLOW_DEFINITION,))

_EDGES = (
    (
        "web.requirements_approve",
        WebLifecycleStatus.DRAFT,
        WebLifecycleStatus.REQUIREMENTS_APPROVED,
    ),
    (
        "web.architecture_approve",
        WebLifecycleStatus.REQUIREMENTS_APPROVED,
        WebLifecycleStatus.ARCHITECTURE_APPROVED,
    ),
    ("web.ui_approve", WebLifecycleStatus.ARCHITECTURE_APPROVED, WebLifecycleStatus.UI_APPROVED),
    (
        "web.implementation_ready",
        WebLifecycleStatus.UI_APPROVED,
        WebLifecycleStatus.IMPLEMENTATION_READY,
    ),
    (
        "web.frontend.implementing",
        WebLifecycleStatus.IMPLEMENTATION_READY,
        WebLifecycleStatus.IMPLEMENTING,
    ),
    ("web.qa.testing", WebLifecycleStatus.IMPLEMENTING, WebLifecycleStatus.TESTING),
    ("web.qa.release_ready", WebLifecycleStatus.TESTING, WebLifecycleStatus.RELEASE_READY),
    ("web.release.deployed", WebLifecycleStatus.RELEASE_READY, WebLifecycleStatus.DEPLOYED),
)


def _transition_definition(
    index: int,
    transition_key: str,
    source: WebLifecycleStatus,
    destination: WebLifecycleStatus,
) -> WorkflowTransitionDefinition:
    return WorkflowTransitionDefinition(
        transition_id=TransitionId(f"TRN-01HZX7M3FQ1T2Q9V8Y6K4C2R{40 + index:02d}"),
        name=f"Advance Web lifecycle from {source.value} to {destination.value}",
        transition_key=transition_key,
        contract_version=_CONTRACT_VERSION,
        domain=TransitionDomain.WORKFLOW_STATE,
        from_states=(source.value,),
        to_state=destination.value,
        effects=(
            TransitionEffect(
                effect_type=EffectType.SET_FIELD,
                path_template="/workflows/{entity_id}/current_state",
                value_source=EffectValueSource.TO_STATE,
            ),
        ),
        workflow_namespace=WEB_WORKFLOW_NAMESPACE,
        workflow_definition_version=WEB_WORKFLOW_DEFINITION_VERSION,
        workflow_definition_fingerprint=WEB_WORKFLOW_DEFINITION.definition_fingerprint(),
    )


WEB_TRANSITION_DEFINITIONS = tuple(
    _transition_definition(index, key, source, destination)
    for index, (key, source, destination) in enumerate(_EDGES)
)
WEB_TRANSITION_REGISTRY = TransitionRegistry(
    WEB_TRANSITION_DEFINITIONS,
    workflow_definitions=WEB_WORKFLOW_DEFINITION_REGISTRY.definitions,
)
WEB_TRANSITION_KEYS = {(source, destination): key for key, source, destination in _EDGES}


def initialize_web_lifecycle(
    runtime: Runtime, command: InitializeWebLifecycleCommand
) -> InitializeWorkflowResult:
    """Initialize only the canonical DRAFT state through public Runtime authority."""

    return runtime.initialize_workflow(
        InitializeWorkflowCommand(
            idempotency_key=command.idempotency_key,
            project_id=ProjectId(command.project_id),
            workflow_id=WEB_WORKFLOW_ID,
            workflow_namespace=WEB_WORKFLOW_NAMESPACE,
            definition_version=WEB_WORKFLOW_DEFINITION_VERSION,
            definition_fingerprint=WEB_WORKFLOW_DEFINITION.definition_fingerprint(),
            expected_record_version=command.expected_record_version,
            expected_record_fingerprint=command.expected_record_fingerprint,
            expected_content_fingerprint=command.expected_content_fingerprint,
            actor_id=command.actor_id,
            actor_display_name=command.actor_display_name,
        )
    )


def read_web_lifecycle(runtime: Runtime, project_id: str) -> WebLifecycleEvidence:
    """Read and verify the exact Web workflow record from Runtime."""

    loaded = runtime.get_project(ProjectId(project_id))
    record = loaded.state.workflow_registry.get(WEB_WORKFLOW_ID)
    if record is None:
        raise WebWorkflowAuthorityError("Web workflow not initialized")
    if (
        record.workflow_id != WEB_WORKFLOW_ID
        or record.namespace != WEB_WORKFLOW_NAMESPACE
        or record.definition_version != WEB_WORKFLOW_DEFINITION_VERSION
        or record.definition_fingerprint != WEB_WORKFLOW_DEFINITION.definition_fingerprint()
        or record.current_state not in WEB_WORKFLOW_DEFINITION.allowed_states
    ):
        raise WebWorkflowAuthorityError("Web workflow definition binding is invalid")
    try:
        current = WebLifecycleStatus(str(record.current_state))
    except ValueError as error:
        raise WebWorkflowAuthorityError("Web workflow state is unsupported") from error
    return WebLifecycleEvidence(
        project_id=loaded.project_id,
        workflow_id=record.workflow_id,
        workflow_namespace=record.namespace,
        definition_version=record.definition_version,
        definition_fingerprint=record.definition_fingerprint,
        current_status=current,
        aggregate_record_version=loaded.record_version,
        aggregate_record_fingerprint=loaded.record_fingerprint,
        aggregate_content_fingerprint=loaded.content_fingerprint,
        workflow_record_version=record.record_version,
        workflow_content_fingerprint=compute_content_fingerprint(record),
    )


def build_web_transition_command(
    runtime: Runtime,
    *,
    project_id: str,
    asserted_status: WebLifecycleStatus,
    asserted_runtime_state: str,
    destination: WebLifecycleStatus,
    transition_key: str,
    idempotency_key: str,
    request_id: str,
    expected_record_version: int,
    expected_record_fingerprint: str,
    expected_content_fingerprint: str,
    expected_workflow_record_version: int | None,
    expected_workflow_content_fingerprint: str | None,
    metadata: dict[str, str],
    actor_id: str,
    actor_display_name: str | None,
) -> ApplyTransitionCommand:
    """Bind one adjacent Web edge to verified aggregate and workflow CAS evidence."""

    evidence = read_web_lifecycle(runtime, project_id)
    expected_sources = tuple(
        source
        for (source, target), key in WEB_TRANSITION_KEYS.items()
        if target is destination and key == transition_key
    )
    if len(expected_sources) != 1:
        raise WebWorkflowAuthorityError("Web lifecycle transition is not an allowed adjacent edge")
    source = expected_sources[0]
    if asserted_status is not source or asserted_runtime_state != source.value:
        raise WebWorkflowAuthorityError("Caller lifecycle assertion disagrees with Runtime")
    retry = evidence.current_status is destination
    if evidence.current_status is not source and not retry:
        raise WebWorkflowAuthorityError("Caller lifecycle assertion disagrees with Runtime")
    if retry:
        if (
            expected_workflow_record_version is None
            or expected_workflow_content_fingerprint is None
        ):
            raise WebWorkflowAuthorityError("Exact retry requires pinned workflow preconditions")
    else:
        if (
            expected_record_version != evidence.aggregate_record_version
            or expected_record_fingerprint != evidence.aggregate_record_fingerprint
            or expected_content_fingerprint != evidence.aggregate_content_fingerprint
        ):
            raise WebWorkflowAuthorityError("Runtime aggregate evidence is stale")
        if expected_workflow_record_version is not None and (
            expected_workflow_record_version != evidence.workflow_record_version
            or expected_workflow_content_fingerprint != evidence.workflow_content_fingerprint
        ):
            raise WebWorkflowAuthorityError("Runtime workflow evidence is stale")
    target_record_version = (
        evidence.workflow_record_version
        if expected_workflow_record_version is None
        else expected_workflow_record_version
    )
    target_content_fingerprint = (
        evidence.workflow_content_fingerprint
        if expected_workflow_content_fingerprint is None
        else expected_workflow_content_fingerprint
    )
    return ApplyTransitionCommand.model_validate(
        {
            "idempotency_key": idempotency_key,
            "project_id": evidence.project_id,
            "request_id": ChangeId(request_id),
            "target": TransitionTarget(
                domain=TransitionDomain.WORKFLOW_STATE,
                entity_id=evidence.workflow_id,
            ),
            "transition_key": transition_key,
            "expected_from_state": source.value,
            "expected_record_version": expected_record_version,
            "expected_record_fingerprint": expected_record_fingerprint,
            "expected_content_fingerprint": expected_content_fingerprint,
            "expected_target_record_version": target_record_version,
            "expected_target_content_fingerprint": target_content_fingerprint,
            "metadata": metadata,
            "actor_id": actor_id,
            "actor_display_name": actor_display_name,
        },
        strict=True,
    )


__all__ = (
    "WEB_TRANSITION_DEFINITIONS",
    "WEB_TRANSITION_KEYS",
    "WEB_TRANSITION_REGISTRY",
    "WEB_WORKFLOW_DEFINITION",
    "WEB_WORKFLOW_DEFINITION_REGISTRY",
    "WEB_WORKFLOW_DEFINITION_VERSION",
    "WEB_WORKFLOW_ID",
    "WEB_WORKFLOW_NAMESPACE",
    "InitializeWebLifecycleCommand",
    "WebLifecycleEvidence",
    "WebWorkflowAuthorityError",
    "build_web_transition_command",
    "initialize_web_lifecycle",
    "read_web_lifecycle",
)
