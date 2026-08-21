"""W07 canonical contracts and fail-closed invariants."""

from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
from pathlib import Path

import pytest

from arch_web import (
    ApplicationMigrationPlan,
    ApplicationMigrationStep,
    BackendDataBinding,
    BackendDisposition,
    BackendEngineeringCheck,
    BackendFinding,
    BackendFindingCode,
    BackendReviewPackage,
    BindingClosureStatus,
    ContractRef,
    DataFieldSpec,
    DataSensitivity,
    ExternalIntegrationContract,
    FrontendCheckStatus,
    ReconciliationStatus,
    apply_backend_unit,
    decode_contract,
    encode_contract,
    verify_backend,
)
from arch_web.application.backend.models import VerifyBackendCommand
from arch_web.contracts.versions import CURRENT_WEB_CONTRACT_VERSION
from w07.factories import backend_bundle


def test_top_level_backend_records_round_trip(tmp_path: Path) -> None:
    _, workspace, frontend, _, prepared, adapter, proposal, apply, _ = backend_bundle(tmp_path)
    applied = apply_backend_unit(apply)
    completion = verify_backend(
        VerifyBackendCommand(
            apply.project_status, prepared.assignment, applied, workspace, frontend, ()
        ),
        adapter,
    ).completion
    review = BackendReviewPackage(
        CURRENT_WEB_CONTRACT_VERSION,
        "BRV-test",
        completion.project_id,
        ContractRef(
            completion.contract_type,
            completion.completion_id,
            completion.contract_version,
            completion.canonical_fingerprint(),
        ),
        completion.findings,
        completion.disposition,
    )
    for record in (prepared.assignment, proposal, completion, review):
        assert decode_contract(type(record), encode_contract(record)) == record
    with pytest.raises(FrozenInstanceError):
        proposal.proposal_id = "changed"


def test_contract_invariants_fail_closed(tmp_path: Path) -> None:
    *_, proposal, _, _ = backend_bundle(tmp_path)
    with pytest.raises(ValueError, match="required field"):
        DataFieldSpec(
            "field", "string", True, True, False, True, DataSensitivity.INTERNAL, "purpose"
        )
    with pytest.raises(ValueError, match="operation"):
        BackendDataBinding("binding", None, BindingClosureStatus.IMPLEMENTED)
    with pytest.raises(ValueError, match="authority"):
        BackendDataBinding("binding", None, BindingClosureStatus.DEFERRED_WITH_AUTHORITY)
    with pytest.raises(ValueError, match="signature"):
        ExternalIntegrationContract(
            "hook",
            "provider",
            "inbound_webhook",
            "event",
            "HOOK_SECRET",
            2,
            "none",
            True,
            False,
            "none",
            "redacted",
        )
    with pytest.raises(ValueError, match="Passing"):
        BackendEngineeringCheck(
            "check", "lint", "adapter", "1", "tree", FrontendCheckStatus.PASS, 1, "digest"
        )
    assert proposal.bindings == tuple(
        sorted(proposal.bindings, key=lambda item: item.frontend_binding_ref)
    )


def test_migration_chain_and_completion_cannot_hide_risk(tmp_path: Path) -> None:
    _, workspace, frontend, _, prepared, adapter, _, apply, _ = backend_bundle(tmp_path)
    applied = apply_backend_unit(apply)
    completion = verify_backend(
        VerifyBackendCommand(
            apply.project_status, prepared.assignment, applied, workspace, frontend, ()
        ),
        adapter,
    ).completion
    step = ApplicationMigrationStep(
        "second", "missing", "2", "checksum", "SELECT 1", False, "none", ("ok",)
    )
    with pytest.raises(ValueError, match="root"):
        ApplicationMigrationPlan(CURRENT_WEB_CONTRACT_VERSION, "plan", "app", (step,))
    destructive = BackendFinding("finding", BackendFindingCode.DESTRUCTIVE_MIGRATION, "blocked")
    with pytest.raises(ValueError, match="contradicts"):
        replace(completion, findings=(destructive,))
    with pytest.raises(ValueError, match="IMPLEMENTING"):
        replace(completion, runtime_state=completion.runtime_state.TESTING)
    with pytest.raises(ValueError, match="NOT_APPLICABLE"):
        replace(
            completion,
            disposition=BackendDisposition.NOT_APPLICABLE,
            findings=(),
            engineering_checks=(),
        )
    with pytest.raises(ValueError, match="contradicts"):
        replace(completion, reconciliation_status=ReconciliationStatus.REQUIRED)
