"""Property tests for deterministic W06 evidence."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from arch_web import (
    FrontendFinding,
    FrontendFindingCode,
    FrontendReadiness,
    prepare_frontend,
    proposal_to_change_set,
)
from w06.factories import prepared_frontend, proposal_bundle


@pytest.mark.property
@settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(st.booleans())
def test_assignment_order_does_not_change_fingerprint(tmp_path: Path, reverse: bool) -> None:
    *_, command, prepared = prepared_frontend(tmp_path)
    units = tuple(reversed(command.selected_unit_refs)) if reverse else command.selected_unit_refs
    assert prepare_frontend(replace(command, selected_unit_refs=units)) == prepared


@pytest.mark.property
@settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(st.sampled_from(["one", "two", "three", "semantic-change"]))
def test_semantic_artifact_mutation_changes_proposal_fingerprint(
    tmp_path: Path, suffix: str
) -> None:
    *_, proposal, _, _ = proposal_bundle(tmp_path)
    artifact = proposal.artifacts[0]
    changed = replace(artifact, content=artifact.content + suffix)
    mutated = replace(proposal, artifacts=(changed, *proposal.artifacts[1:]))
    assert mutated.canonical_fingerprint() != proposal.canonical_fingerprint()


@pytest.mark.property
@settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(st.permutations((0, 1, 2)))
def test_fixed_proposal_changes_are_order_invariant(tmp_path: Path, order: tuple[int, ...]) -> None:
    *_, apply = proposal_bundle(tmp_path)
    proposal = replace(
        apply.proposal,
        artifacts=tuple(apply.proposal.artifacts[index] for index in order),
    )
    assert proposal_to_change_set(replace(apply, proposal=proposal)) == proposal_to_change_set(
        apply
    )


def test_blocking_finding_cannot_form_complete_package(tmp_path: Path) -> None:
    from arch_web import VerifyFrontendCommand, apply_frontend_unit, verify_frontend

    _, workspace, _, prepared, adapter, _, authorization, apply = proposal_bundle(tmp_path)
    applied = apply_frontend_unit(apply)
    finding = FrontendFinding(
        "finding:block",
        FrontendFindingCode.DESIGN_DRIFT,
        "blocked",
    )
    proposal = replace(applied.proposal, findings=(finding,))
    blocked_applied = replace(applied, proposal=proposal)
    result = verify_frontend(
        VerifyFrontendCommand(
            apply.project_status,
            prepared.assignment,
            authorization,
            blocked_applied,
            workspace,
            (),
        ),
        adapter,
    )
    assert result.completion.readiness is FrontendReadiness.BLOCKED
