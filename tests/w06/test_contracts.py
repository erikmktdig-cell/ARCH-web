"""W06 canonical contracts and invariants."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import FrozenInstanceError, replace
from pathlib import Path
from typing import Any, cast

import pytest

from arch_web import (
    FrontendCheckStatus,
    FrontendCompletionPackage,
    FrontendDependencyDecision,
    FrontendEngineeringCheck,
    FrontendFinding,
    FrontendFindingCode,
    FrontendReadiness,
    FrontendReviewPackage,
    ReconciliationStatus,
    apply_frontend_unit,
    decode_contract,
    encode_contract,
    verify_frontend,
)
from arch_web.application.frontend.models import VerifyFrontendCommand
from arch_web.contracts.versions import CURRENT_WEB_CONTRACT_VERSION
from arch_web.domain.references import ContractRef
from w06.factories import proposal_bundle


def test_top_level_frontend_records_round_trip(tmp_path: Path) -> None:
    _, workspace, _, prepared, adapter, proposal, authorization, apply = proposal_bundle(tmp_path)
    applied = apply_frontend_unit(apply)
    completion = verify_frontend(
        VerifyFrontendCommand(
            apply.project_status,
            prepared.assignment,
            authorization,
            applied,
            workspace,
            (),
        ),
        adapter,
    ).completion
    review = FrontendReviewPackage(
        CURRENT_WEB_CONTRACT_VERSION,
        "FRV-test",
        completion.project_id,
        ContractRef(
            completion.contract_type,
            completion.completion_id,
            completion.contract_version,
            completion.canonical_fingerprint(),
        ),
        completion.findings,
        completion.readiness,
    )
    records = (prepared.assignment, proposal, authorization, completion, review)
    for record in records:
        payload = encode_contract(record)
        assert decode_contract(type(record), payload) == record
        assert type(record).from_data(cast(Mapping[str, Any], record.canonical_data())) == record


def test_frontend_records_are_deeply_tuple_normalized_and_frozen(tmp_path: Path) -> None:
    *_, proposal, _, _ = proposal_bundle(tmp_path)
    with pytest.raises(FrozenInstanceError):
        proposal.proposal_id = "changed"
    assert isinstance(proposal.artifacts, tuple)
    assert isinstance(proposal.component_bindings[0].implemented_states, tuple)


@pytest.mark.parametrize("version", ["latest", "*", "^1.0", "~1.2"])
def test_dependency_versions_are_exact(version: str) -> None:
    with pytest.raises(ValueError, match="exact"):
        FrontendDependencyDecision("library", version, True, "approved")


def test_passing_check_rejects_failure_exit_status() -> None:
    with pytest.raises(ValueError, match="Passing"):
        FrontendEngineeringCheck(
            "check",
            "build",
            "adapter",
            "1",
            "tree",
            FrontendCheckStatus.PASS,
            1,
            "digest",
        )


def test_completion_cannot_hide_blocker_or_reconciliation(tmp_path: Path) -> None:
    _, workspace, _, prepared, adapter, _, authorization, apply = proposal_bundle(tmp_path)
    applied = apply_frontend_unit(apply)
    completion = verify_frontend(
        VerifyFrontendCommand(
            apply.project_status,
            prepared.assignment,
            authorization,
            applied,
            workspace,
            (),
        ),
        adapter,
    ).completion
    finding = FrontendFinding(
        "finding",
        FrontendFindingCode.DESIGN_DRIFT,
        "drift",
    )
    with pytest.raises(ValueError, match="contradicts"):
        replace(completion, findings=(finding,))
    with pytest.raises(ValueError, match="contradicts"):
        replace(completion, reconciliation_status=ReconciliationStatus.REQUIRED)


def test_completion_never_accepts_testing_state(tmp_path: Path) -> None:
    *_, apply = proposal_bundle(tmp_path)
    applied = apply_frontend_unit(apply)
    with pytest.raises(ValueError, match="IMPLEMENTING"):
        FrontendCompletionPackage(
            CURRENT_WEB_CONTRACT_VERSION,
            "completion",
            apply.assignment.project_id,
            apply.assignment.runtime_state,
            ContractRef(
                apply.authorization.contract_type,
                apply.authorization.authorization_id,
                apply.authorization.contract_version,
                apply.authorization.canonical_fingerprint(),
            ),
            apply.assignment.implementation_plan_fingerprint,
            apply.proposal.canonical_fingerprint(),
            applied.receipt.change_set_fingerprint,
            applied.receipt,
            apply.assignment.managed_tree_fingerprint,
            applied.receipt.post_tree_fingerprint,
            "adapter",
            (),
            (),
            (),
            ReconciliationStatus.CLEAN,
            (),
            FrontendReadiness.COMPLETE_FOR_REVIEW,
        )
