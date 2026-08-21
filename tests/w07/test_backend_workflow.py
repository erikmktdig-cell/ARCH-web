"""W07 governed backend workflow tests."""

from __future__ import annotations

import hashlib
from dataclasses import replace
from pathlib import Path

import pytest

from arch_web import (
    ApplicationSQLiteHarness,
    BackendDisposition,
    BackendFindingCode,
    BackendPreparationError,
    BackendProposalError,
    LocalIntegrationDouble,
    PrepareBackendCommand,
    VerifyBackendCommand,
    WebLifecycleStatus,
    apply_backend_unit,
    backend_proposal_findings,
    backend_proposal_to_change_set,
    prepare_backend,
    verify_backend,
)
from w07.factories import backend_bundle


def test_assignment_is_deterministic(tmp_path: Path) -> None:
    *_, command, prepared, _, _, _, _ = backend_bundle(tmp_path)
    assert prepare_backend(command) == prepared
    assert prepared.assignment.runtime_state is WebLifecycleStatus.IMPLEMENTING


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("project_status", WebLifecycleStatus.TESTING),
        ("project_id", "wrong"),
        ("requirements_fingerprint", "stale"),
    ],
)
def test_preconditions_fail_closed(tmp_path: Path, field: str, value: object) -> None:
    *_, command, _, _, _, _, _ = backend_bundle(tmp_path)
    with pytest.raises(BackendPreparationError):
        prepare_backend(replace(command, **{field: value}))


def test_static_project_is_exact_not_applicable(tmp_path: Path) -> None:
    _, workspace, completion, command, _, _, _, _, _ = backend_bundle(tmp_path)
    static_completion = replace(completion, w07_handoff=())
    static_command = replace(
        command,
        frontend_completion=static_completion,
        selected_unit_refs=(),
        interface=None,
        data_contract=None,
        authentication=None,
        authorization_rules=(),
        persistence=None,
        migrations=None,
        integrations=(),
    )
    result = prepare_backend(static_command)
    assert result.not_applicable_completion is not None
    assert result.not_applicable_completion.disposition is BackendDisposition.NOT_APPLICABLE
    assert result.execution_workspace.plan == workspace.plan


def test_contract_and_security_findings_block(tmp_path: Path) -> None:
    _, workspace, _, _, prepared, _, proposal, _, _ = backend_bundle(tmp_path)
    artifact = proposal.artifacts[0]
    content = 'password="actual-secret"\nconnection.execute(f"SELECT {value}")\n'
    changed_artifact = replace(
        artifact,
        content=content,
        content_fingerprint="sha256:" + hashlib.sha256(content.encode()).hexdigest(),
    )
    changed = replace(proposal, artifacts=(changed_artifact, *proposal.artifacts[1:]))
    codes = {
        item.code for item in backend_proposal_findings(prepared.assignment, changed, workspace)
    }
    assert BackendFindingCode.SECRET_EXPOSURE in codes
    assert BackendFindingCode.INJECTION_RISK in codes


def test_proposal_to_w05_is_deterministic_and_dry(tmp_path: Path) -> None:
    *_, apply, _ = backend_bundle(tmp_path)
    first = backend_proposal_to_change_set(apply)
    assert first == backend_proposal_to_change_set(apply)
    assert not any((tmp_path / path).exists() for path, _ in first[1])


def test_reference_vertical_slice_completes_without_transition(tmp_path: Path) -> None:
    _, workspace, frontend, _, prepared, adapter, proposal, apply, _ = backend_bundle(tmp_path)
    applied = apply_backend_unit(apply)
    result = verify_backend(
        VerifyBackendCommand(
            WebLifecycleStatus.IMPLEMENTING,
            prepared.assignment,
            applied,
            workspace,
            frontend,
            ("authorization", "migration", "repository", "security"),
        ),
        adapter,
    )
    assert result.completion.disposition is BackendDisposition.COMPLETE_FOR_REVIEW
    assert result.completion.runtime_state is WebLifecycleStatus.IMPLEMENTING
    assert all((tmp_path / artifact.path).is_file() for artifact in proposal.artifacts)


def test_stale_workspace_and_blocking_proposal_never_mutate(tmp_path: Path) -> None:
    *_, apply, _ = backend_bundle(tmp_path)
    stale = replace(
        apply.prepared_workspace,
        baseline=replace(apply.prepared_workspace.baseline, tree_fingerprint="stale"),
    )
    with pytest.raises(BackendProposalError):
        apply_backend_unit(replace(apply, prepared_workspace=stale))
    assert not (tmp_path / "src/backend/service.py").exists()


def test_application_sqlite_is_separate_migrated_and_authoritative(tmp_path: Path) -> None:
    *_, contracts = backend_bundle(tmp_path / "workspace")
    _, _, _, rules, _, migrations, _ = contracts
    app_db, runtime_db = tmp_path / "application.sqlite", tmp_path / "runtime.sqlite"
    with ApplicationSQLiteHarness(app_db, runtime_db) as store:
        store.migrate(migrations)
        store.migrate(migrations)
        store.insert_owned_item("item-1", "alice", "Approved")
        assert store.item_for_actor("item-1", "alice", rules[0])[-1] == "Approved"
        with pytest.raises(PermissionError):
            store.item_for_actor("item-1", "bob", rules[0])
        with pytest.raises(ValueError, match="validation"):
            store.insert_owned_item("item-2", "alice", "")
    assert app_db.exists()
    assert not runtime_db.exists()
    with pytest.raises(ValueError, match="separate"):
        ApplicationSQLiteHarness(app_db, app_db)


def test_local_integration_idempotency_has_no_network() -> None:
    double = LocalIntegrationDouble()
    calls = 0

    def action() -> str:
        nonlocal calls
        calls += 1
        return "accepted"

    assert double.execute("key", "request-a", action) == "accepted"
    assert double.execute("key", "request-a", action) == "accepted"
    assert calls == 1
    with pytest.raises(ValueError, match="conflict"):
        double.execute("key", "request-b", action)


def test_contract_invariants_reject_unsafe_semantics(tmp_path: Path) -> None:
    *_, command, _, _, _, _, contracts = backend_bundle(tmp_path)
    _, data, auth, _, persistence, _, _ = contracts
    with pytest.raises(ValueError, match="separate"):
        replace(persistence, application_store_ref=persistence.runtime_store_ref)
    with pytest.raises(ValueError, match="client identity"):
        replace(auth, client_identity_trusted=True)
    with pytest.raises(ValueError, match="Indefinite"):
        replace(data.entities[0].lifecycle, retention_policy="forever")
    assert isinstance(command, PrepareBackendCommand)
