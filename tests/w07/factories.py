"""Exact W06-to-W07 reference fixture."""

from __future__ import annotations

import hashlib
from dataclasses import replace
from pathlib import Path
from typing import Any

from arch_web import (
    ApplicationDataContract,
    ApplicationMigrationPlan,
    ApplicationMigrationStep,
    ApplyBackendUnitCommand,
    ApplyFrontendUnitCommand,
    AuthenticationContract,
    AuthorizationRule,
    BackendInterfaceContract,
    BackendOperationContract,
    DataEntitySpec,
    DataFieldSpec,
    DataLifecyclePolicy,
    DataOwnershipPolicy,
    DataSensitivity,
    DataSourceKind,
    FailureKind,
    FailurePolicy,
    FrontendDataBinding,
    FrontendDataDisposition,
    FrontendExecutionAuthorization,
    ImplementationUnit,
    ImplementationUnitKind,
    PathClaim,
    PathClaimMode,
    PersistenceContract,
    PrepareBackendCommand,
    PythonSQLiteBackendAdapter,
    StaticFrontendAdapter,
    VerifyFrontendCommand,
    WebLifecycleStatus,
    WorkspaceExecutionPolicy,
    apply_frontend_unit,
    prepare_backend,
    prepare_frontend,
    verify_frontend,
)
from arch_web.contracts.versions import CURRENT_WEB_CONTRACT_VERSION
from w06.factories import prepared_frontend


def contract_bundle(project_id: str, binding_refs: tuple[str, ...]) -> tuple[Any, ...]:
    fields = (
        DataFieldSpec(
            "item_id",
            "string",
            True,
            False,
            True,
            False,
            DataSensitivity.INTERNAL,
            "Stable identity",
        ),
        DataFieldSpec(
            "owner_id",
            "string",
            True,
            False,
            False,
            False,
            DataSensitivity.PERSONAL,
            "Server ownership",
        ),
        DataFieldSpec(
            "title",
            "string",
            True,
            False,
            False,
            True,
            DataSensitivity.INTERNAL,
            "Approved display title",
        ),
    )
    entity = DataEntitySpec(
        "item",
        "Persist approved dashboard items",
        "item_id",
        fields,
        DataOwnershipPolicy(
            "project-user",
            DataSourceKind.USER_GENERATED,
            "owner-only",
            "owner export",
            ("redact owner_id",),
        ),
        DataLifecyclePolicy(
            "delete with project", "hard delete after export window", None, "write audit metadata"
        ),
        ("REQ-core",),
        ("get_item", "create_item"),
    )
    data = ApplicationDataContract(CURRENT_WEB_CONTRACT_VERSION, "ADC-items", project_id, (entity,))
    rule = AuthorizationRule(
        "AUTHZ-owner",
        "authenticated-user",
        "read-write",
        "item",
        "owner_id == subject_id",
        True,
        ("REQ-core",),
    )
    operation = BackendOperationContract(
        "get_item",
        "Return the approved item view",
        ("item.item_id",),
        ("item.item_id", "item.title"),
        (FailureKind.UNAUTHENTICATED, FailureKind.UNAUTHORIZED, FailureKind.NOT_FOUND),
        True,
        rule.rule_id,
        False,
        None,
        DataSensitivity.INTERNAL,
        ("REQ-core",),
        ("surface:overview",),
        binding_refs,
    )
    interface = BackendInterfaceContract(
        CURRENT_WEB_CONTRACT_VERSION,
        "BIC-items",
        project_id,
        "in-process-call",
        (operation,),
        tuple(FailurePolicy(kind, kind.value, "error", False) for kind in operation.failure_kinds),
    )
    auth = AuthenticationContract(
        CURRENT_WEB_CONTRACT_VERSION,
        "AUC-local",
        "injected-principal",
        "approved-host",
        "trusted-server-context",
        (),
    )
    persistence = PersistenceContract(
        CURRENT_WEB_CONTRACT_VERSION,
        "PSC-app",
        "sqlite@3",
        "application-db",
        "arch-runtime-db",
        ("item-repository",),
        "single-operation transaction",
        "serializable writes",
        "APP_DATABASE_PATH",
    )
    statement = (
        "CREATE TABLE app_items (item_id TEXT PRIMARY KEY, "
        "owner_id TEXT NOT NULL, title TEXT NOT NULL);"
    )
    migration = ApplicationMigrationStep(
        "app-0001",
        None,
        "1",
        "sha256:" + hashlib.sha256(statement.encode()).hexdigest(),
        statement,
        False,
        "drop disposable database",
        ("app_items exists",),
    )
    migrations = ApplicationMigrationPlan(
        CURRENT_WEB_CONTRACT_VERSION, "AMP-items", "application-db", (migration,)
    )
    return interface, data, auth, (rule,), persistence, migrations, ()


def backend_bundle(root: Path) -> tuple[Any, ...]:
    source, workspace, receipt, frontend_command, _ = prepared_frontend(root)
    unit = ImplementationUnit(
        "unit:backend",
        ImplementationUnitKind.BACKEND,
        "Implement the approved item boundary",
        ("REQ-core",),
        ("surface:overview",),
        (),
        (),
        ("src/backend/**",),
        (),
        ("backend contract", "migration test", "authorization test"),
        "backend-engineer",
        "standard",
        ("W08", "W09", "runtime persistence"),
    )
    claim = PathClaim("claim:backend", unit.unit_id, "src/backend/**", PathClaimMode.EXCLUSIVE)
    plan = replace(
        workspace.plan,
        units=(*workspace.plan.units, unit),
        path_claims=(*workspace.plan.path_claims, claim),
    )
    stack = replace(workspace.stack, language="python@3.12", backend_model="python-stdlib-sqlite@3")
    workspace = replace(workspace, plan=plan, stack=stack)
    receipt = replace(
        receipt,
        implementation_plan_fingerprint=plan.canonical_fingerprint(),
        resolved_stack_fingerprint=stack.canonical_fingerprint(),
    )
    frontend_command = replace(
        frontend_command, prepared_workspace=workspace, workspace_receipt=receipt
    )
    prepared = prepare_frontend(frontend_command)
    frontend_adapter = StaticFrontendAdapter()
    frontend_proposal = frontend_adapter.reference_proposal(
        prepared.assignment, frontend_command.design_system, frontend_command.ui_specification, plan
    )
    if not frontend_proposal.data_bindings:
        frontend_proposal = replace(
            frontend_proposal,
            data_bindings=(
                FrontendDataBinding(
                    "FDB-w07-item",
                    prepared.assignment.component_refs[0],
                    FrontendDataDisposition.PENDING_BACKEND_BINDING,
                    "ItemDataSource",
                ),
            ),
        )
    authorization = FrontendExecutionAuthorization(
        CURRENT_WEB_CONTRACT_VERSION,
        "FAU-w07",
        frontend_command.project_id,
        prepared.assignment.canonical_fingerprint(),
        plan.canonical_fingerprint(),
        receipt.canonical_fingerprint(),
        frontend_command.runtime_record_version,
        frontend_command.runtime_record_fingerprint,
        True,
    )
    applied_frontend = apply_frontend_unit(
        ApplyFrontendUnitCommand(
            "execution:w07-frontend",
            WebLifecycleStatus.IMPLEMENTING,
            prepared.assignment,
            authorization,
            frontend_proposal,
            prepared.execution_workspace,
            source.target,
            WorkspaceExecutionPolicy(),
        )
    )
    completion = verify_frontend(
        VerifyFrontendCommand(
            WebLifecycleStatus.IMPLEMENTING,
            prepared.assignment,
            authorization,
            applied_frontend,
            workspace,
            (),
        ),
        frontend_adapter,
    ).completion
    current = replace(
        frontend_command.current_baseline,
        files=applied_frontend.receipt.changed_paths,
        tree_fingerprint=applied_frontend.receipt.post_tree_fingerprint,
        repository=replace(
            frontend_command.current_baseline.repository,
            head=applied_frontend.receipt.repository_evidence.after_head,
        ),
    )
    contracts = contract_bundle(frontend_command.project_id, completion.w07_handoff)
    command = PrepareBackendCommand(
        frontend_command.project_id,
        WebLifecycleStatus.IMPLEMENTING,
        7,
        "sha256:" + "b" * 64,
        frontend_command.requirements_fingerprint,
        frontend_command.architecture,
        workspace,
        completion,
        frontend_proposal,
        current,
        (unit.unit_id,),
        *contracts,
    )
    prepared_backend = prepare_backend(command)
    adapter = PythonSQLiteBackendAdapter()
    proposal = adapter.reference_proposal(
        prepared_backend.assignment, *contracts[:-1], contracts[-1], plan
    )
    apply = ApplyBackendUnitCommand(
        "execution:w07-backend",
        WebLifecycleStatus.IMPLEMENTING,
        prepared_backend.assignment,
        proposal,
        prepared_backend.execution_workspace,
        source.target,
        WorkspaceExecutionPolicy(),
    )
    return (
        source,
        workspace,
        completion,
        command,
        prepared_backend,
        adapter,
        proposal,
        apply,
        contracts,
    )
