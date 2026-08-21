"""W05 canonical contracts and invariant tests."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import FrozenInstanceError, replace
from pathlib import Path
from typing import Any, cast

import pytest

from arch_web import (
    ContractRef,
    ExecutionOutcome,
    ReconciliationStatus,
    WorkspaceFinding,
    WorkspaceFindingCode,
    WorkspaceReadiness,
    decode_contract,
    encode_contract,
    prepare_workspace,
)
from arch_web.application.workspace.execution import WorkspaceExecutor
from arch_web.application.workspace.models import ApplyWorkspaceCommand
from w05.factories import workspace_command


def test_top_level_workspace_contracts_round_trip(tmp_path: Path) -> None:
    command = workspace_command(tmp_path / "new", new=True)
    prepared = prepare_workspace(command)
    receipt = (
        WorkspaceExecutor()
        .apply(ApplyWorkspaceCommand("roundtrip", command.target, prepared, command.policy))
        .receipt
    )
    records = (
        command.target,
        command.baseline,
        prepared.stack,
        prepared.plan,
        prepared.change_set,
        prepared.review,
        receipt,
    )
    for record in records:
        payload = encode_contract(record)
        assert decode_contract(type(record), payload) == record
        assert type(record).from_data(cast(Mapping[str, Any], record.canonical_data())) == record


def test_workspace_records_are_frozen(tmp_path: Path) -> None:
    plan = prepare_workspace(workspace_command(tmp_path)).plan
    with pytest.raises(FrozenInstanceError):
        plan.plan_id = "changed"  # type: ignore[misc]
    assert isinstance(plan.units, tuple)
    assert isinstance(plan.path_claims, tuple)


def test_review_and_receipt_invariants(tmp_path: Path) -> None:
    command = workspace_command(tmp_path / "new", new=True)
    prepared = prepare_workspace(command)
    finding = WorkspaceFinding("finding", WorkspaceFindingCode.STALE_BASELINE, "stale")
    with pytest.raises(ValueError, match="NOT_READY"):
        replace(prepared.review, findings=(finding,), readiness=WorkspaceReadiness.READY_FOR_REVIEW)
    with pytest.raises(ValueError, match="approval evidence"):
        replace(prepared.review, readiness=WorkspaceReadiness.APPROVED)
    receipt = (
        WorkspaceExecutor()
        .apply(ApplyWorkspaceCommand("receipt", command.target, prepared, command.policy))
        .receipt
    )
    with pytest.raises(ValueError, match="Reconciliation"):
        replace(
            receipt,
            outcome=ExecutionOutcome.RECONCILIATION_REQUIRED,
            reconciliation_status=ReconciliationStatus.CLEAN,
        )


def test_contract_reference_fingerprint_changes_on_semantic_mutation(tmp_path: Path) -> None:
    prepared = prepare_workspace(workspace_command(tmp_path))
    changed = replace(prepared.stack, network_required=True)
    assert changed.canonical_fingerprint() != prepared.stack.canonical_fingerprint()
    ref = ContractRef(
        changed.contract_type,
        changed.manifest_id,
        changed.contract_version,
        changed.canonical_fingerprint(),
    )
    ref.verify(changed, changed.manifest_id)
