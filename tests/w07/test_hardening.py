"""W07 negative paths, transactions, and deterministic properties."""

from __future__ import annotations

import hashlib
import sqlite3
from dataclasses import replace
from pathlib import Path
from typing import cast

import pytest
from hypothesis import given
from hypothesis import strategies as st

from arch_web import (
    ApplicationMigrationPlan,
    ApplicationMigrationStep,
    ApplicationSQLiteHarness,
    BackendDataBinding,
    BackendDisposition,
    BackendEngineeringCheck,
    BackendFindingCode,
    BackendPreparationError,
    BackendProposalError,
    BindingClosureStatus,
    FrontendCheckStatus,
    FrontendFinding,
    FrontendFindingCode,
    FrontendReadiness,
    ImplementationUnitKind,
    ReconciliationStatus,
    UnsupportedBackendStackError,
    VerifyBackendCommand,
    WebLifecycleStatus,
    apply_backend_unit,
    backend_proposal_findings,
    prepare_backend,
    verify_backend,
)
from arch_web.contracts.versions import CURRENT_WEB_CONTRACT_VERSION
from arch_web.ports.backend import BackendStackAdapter
from w07.factories import backend_bundle


def test_prepare_rejects_each_invalid_upstream_state(tmp_path: Path) -> None:
    _, workspace, completion, command, _, _, _, _, _ = backend_bundle(tmp_path)
    frontend_finding = FrontendFinding(
        "frontend-block", FrontendFindingCode.DESIGN_DRIFT, "blocked"
    )
    blocked = replace(completion, readiness=FrontendReadiness.BLOCKED, findings=(frontend_finding,))
    with pytest.raises(BackendPreparationError, match="blocking"):
        prepare_backend(replace(command, frontend_completion=blocked))
    reconciliation = replace(
        completion,
        readiness=FrontendReadiness.BLOCKED,
        reconciliation_status=ReconciliationStatus.REQUIRED,
    )
    with pytest.raises(BackendPreparationError, match="reconciliation"):
        prepare_backend(replace(command, frontend_completion=reconciliation))
    with pytest.raises(BackendPreparationError, match="unknown"):
        prepare_backend(replace(command, selected_unit_refs=("missing",)))
    frontend_unit = next(
        item.unit_id
        for item in workspace.plan.units
        if item.kind is ImplementationUnitKind.FRONTEND
    )
    with pytest.raises(BackendPreparationError, match="authorized"):
        prepare_backend(replace(command, selected_unit_refs=(frontend_unit,)))
    with pytest.raises(BackendPreparationError, match="complete"):
        prepare_backend(replace(command, selected_unit_refs=(), persistence=None))
    static = replace(completion, w07_handoff=())
    with pytest.raises(BackendPreparationError, match="invented"):
        prepare_backend(replace(command, frontend_completion=static, selected_unit_refs=()))


def test_proposal_binding_contract_and_path_drift_are_findings(tmp_path: Path) -> None:
    _, workspace, _, _, prepared, _, proposal, _, _ = backend_bundle(tmp_path)
    stale = replace(proposal, assignment_fingerprint="sha256:" + "0" * 64)
    invented = replace(proposal, authentication=replace(proposal.authentication, provider="other"))
    escaped = replace(proposal.artifacts[0], path="outside/service.py")
    wrong_hash = replace(proposal.artifacts[0], content_fingerprint="sha256:" + "0" * 64)
    missing_binding = replace(proposal, bindings=())
    unknown_binding = replace(proposal.bindings[0], operation_ref="missing")
    blocked_binding = BackendDataBinding(
        proposal.bindings[0].frontend_binding_ref, None, BindingClosureStatus.BLOCKED
    )
    no_rules = replace(proposal, authorization_rules=())
    migration_drift = replace(
        proposal, migrations=replace(proposal.migrations, application_store_ref="other-app")
    )
    cases = (
        (stale, BackendFindingCode.STALE_EVIDENCE),
        (invented, BackendFindingCode.INVENTED_SEMANTICS),
        (
            replace(proposal, artifacts=(escaped, *proposal.artifacts[1:])),
            BackendFindingCode.PATH_CLAIM_VIOLATION,
        ),
        (
            replace(proposal, artifacts=(wrong_hash, *proposal.artifacts[1:])),
            BackendFindingCode.STALE_EVIDENCE,
        ),
        (missing_binding, BackendFindingCode.UNCLOSED_BINDING),
        (
            replace(proposal, bindings=(unknown_binding,)),
            BackendFindingCode.FRONTEND_BACKEND_MISMATCH,
        ),
        (replace(proposal, bindings=(blocked_binding,)), BackendFindingCode.UNCLOSED_BINDING),
        (no_rules, BackendFindingCode.MISSING_AUTHORIZATION),
        (migration_drift, BackendFindingCode.RUNTIME_PERSISTENCE_COUPLING),
    )
    for changed, expected in cases:
        assert expected in {
            item.code for item in backend_proposal_findings(prepared.assignment, changed, workspace)
        }


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("eval(user_input)", BackendFindingCode.INJECTION_RISK),
        ("requests.get('https://example.test')", BackendFindingCode.HIDDEN_NETWORK),
        ("import arch_runtime", BackendFindingCode.RUNTIME_PERSISTENCE_COUPLING),
        ("logger.info(payload, token)", BackendFindingCode.SENSITIVE_LOGGING),
    ],
)
def test_security_scanners_cover_material_backend_risks(
    tmp_path: Path, source: str, expected: BackendFindingCode
) -> None:
    _, workspace, _, _, prepared, _, proposal, _, _ = backend_bundle(tmp_path)
    artifact = proposal.artifacts[0]
    changed = replace(
        artifact,
        content=source,
        content_fingerprint="sha256:" + hashlib.sha256(source.encode()).hexdigest(),
    )
    findings = backend_proposal_findings(
        prepared.assignment,
        replace(proposal, artifacts=(changed, *proposal.artifacts[1:])),
        workspace,
    )
    assert expected in {item.code for item in findings}


class _FailureAdapter:
    identity = "test.failure@1"

    def __init__(self, *, supported: bool = True) -> None:
        self.supported = supported

    def supports(self, _stack: object) -> bool:
        return self.supported

    def verify(self, _proposal: object, tree: str) -> tuple[BackendEngineeringCheck, ...]:
        return (
            BackendEngineeringCheck(
                "failed-check",
                "lint",
                self.identity,
                "1",
                tree,
                FrontendCheckStatus.FAIL,
                1,
                "digest",
            ),
        )


def test_verification_fails_closed_for_state_stack_and_checks(tmp_path: Path) -> None:
    _, workspace, frontend, _, prepared, _, _, apply, _ = backend_bundle(tmp_path)
    applied = apply_backend_unit(apply)
    command = VerifyBackendCommand(
        WebLifecycleStatus.IMPLEMENTING,
        prepared.assignment,
        applied,
        workspace,
        frontend,
        ("build",),
    )
    with pytest.raises(BackendProposalError, match="IMPLEMENTING"):
        verify_backend(
            replace(command, project_status=WebLifecycleStatus.TESTING),
            cast(BackendStackAdapter, _FailureAdapter()),
        )
    with pytest.raises(UnsupportedBackendStackError, match="unsupported"):
        verify_backend(command, cast(BackendStackAdapter, _FailureAdapter(supported=False)))
    completion = verify_backend(command, cast(BackendStackAdapter, _FailureAdapter())).completion
    assert completion.disposition is BackendDisposition.BLOCKED
    assert {item.code for item in completion.findings} == {
        BackendFindingCode.CHECK_FAILED,
        BackendFindingCode.MISSING_CHECK,
    }


def test_wrong_state_and_w05_secret_policy_prevent_backend_mutation(tmp_path: Path) -> None:
    *_, apply, _ = backend_bundle(tmp_path)
    with pytest.raises(BackendProposalError, match="IMPLEMENTING"):
        apply_backend_unit(replace(apply, project_status=WebLifecycleStatus.TESTING))
    artifact = replace(apply.proposal.artifacts[0], path="src/backend/.env")
    proposal = replace(apply.proposal, artifacts=(artifact, *apply.proposal.artifacts[1:]))
    with pytest.raises(BackendProposalError, match="dry-run"):
        apply_backend_unit(replace(apply, proposal=proposal))
    assert not (tmp_path / "src/backend/.env").exists()


def test_sqlite_migration_integrity_destructive_policy_and_rollback(tmp_path: Path) -> None:
    *_, contracts = backend_bundle(tmp_path / "workspace")
    _, _, _, _, _, migrations, _ = contracts
    app, runtime = tmp_path / "app.sqlite", tmp_path / "runtime.sqlite"
    with ApplicationSQLiteHarness(app, runtime) as store:
        bad_checksum = replace(migrations.steps[0], checksum="sha256:" + "0" * 64)
        with pytest.raises(ValueError, match="checksum"):
            store.migrate(replace(migrations, steps=(bad_checksum,)))
        destructive = replace(migrations.steps[0], destructive=True)
        governed = ApplicationMigrationPlan(
            CURRENT_WEB_CONTRACT_VERSION,
            "destructive",
            "application-db",
            (destructive,),
            "authority:approved",
        )
        with pytest.raises(ValueError, match="destructive"):
            store.migrate(governed)
        invalid_sql = "CREATE TABL broken (id TEXT)"
        invalid = ApplicationMigrationStep(
            "invalid",
            None,
            "1",
            "sha256:" + hashlib.sha256(invalid_sql.encode()).hexdigest(),
            invalid_sql,
            False,
            "rollback",
            ("none",),
        )
        with pytest.raises(ValueError, match="migration failed"):
            store.migrate(
                ApplicationMigrationPlan(
                    CURRENT_WEB_CONTRACT_VERSION, "invalid-plan", "application-db", (invalid,)
                )
            )
        store.migrate(migrations)

        def duplicate(connection: sqlite3.Connection) -> None:
            connection.execute("INSERT INTO app_items VALUES (?, ?, ?)", ("same", "alice", "one"))
            connection.execute("INSERT INTO app_items VALUES (?, ?, ?)", ("same", "alice", "two"))

        with pytest.raises(ValueError, match="transaction failed"):
            store.transaction(duplicate)
        with pytest.raises(PermissionError):
            store.item_for_actor("missing", "", contracts[3][0])


@given(st.permutations(("first", "second")))
def test_migration_order_is_canonical(order: list[str]) -> None:
    steps = {
        "first": ApplicationMigrationStep(
            "first", None, "1", "checksum-1", "SELECT 1", False, "none", ("ok",)
        ),
        "second": ApplicationMigrationStep(
            "second", "first", "2", "checksum-2", "SELECT 2", False, "none", ("ok",)
        ),
    }
    plan = ApplicationMigrationPlan(
        CURRENT_WEB_CONTRACT_VERSION,
        "plan",
        "application-db",
        tuple(steps[item] for item in order),
    )
    assert tuple(item.migration_id for item in plan.steps) == ("first", "second")


@given(
    st.text(
        alphabet=st.characters(whitelist_categories=("L", "N")),
        min_size=1,
        max_size=20,
    )
)
def test_semantic_contract_mutation_changes_fingerprint(title: str) -> None:
    from w07.factories import contract_bundle

    data = contract_bundle("project", ())[1]
    field = data.entities[0].fields[-1]
    changed = replace(field, purpose=title)
    if changed != field:
        entity = replace(data.entities[0], fields=(*data.entities[0].fields[:-1], changed))
        assert (
            replace(data, entities=(entity,)).canonical_fingerprint()
            != data.canonical_fingerprint()
        )
