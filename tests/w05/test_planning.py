"""Deterministic W05 stack, plan, claims, and review tests."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from arch_web import (
    ArchitectureChoice,
    ImplementationPlan,
    PathClaim,
    PathClaimMode,
    WebLifecycleStatus,
    WebRoute,
    WorkspaceExecutionPolicy,
    WorkspaceFindingCode,
    WorkspacePreparationError,
    WorkspaceReadiness,
    prepare_workspace,
    resolve_stack,
)
from w05.factories import stack_profile, workspace_command


@pytest.mark.parametrize("route", list(WebRoute))
def test_every_route_produces_complete_deterministic_plan(tmp_path: Path, route: WebRoute) -> None:
    command = workspace_command(tmp_path / route.value, route)
    first = prepare_workspace(command)
    second = prepare_workspace(command)
    assert first.canonical_bytes() == second.canonical_bytes()
    assert first.review.readiness is WorkspaceReadiness.READY_FOR_REVIEW
    covered = {ref for unit in first.plan.units for ref in unit.surface_refs}
    assert covered == {item.surface_ref for item in command.ui_specification.surfaces}
    assert all(unit.acceptance_evidence for unit in first.plan.units)
    assert all(
        "deployment" in unit.prohibited_scope or unit.kind.value == "shared"
        for unit in first.plan.units
    )


def test_stack_requires_explicit_nonfloating_inputs() -> None:
    with pytest.raises(WorkspacePreparationError, match="unresolved"):
        resolve_stack(replace(stack_profile(), language=ArchitectureChoice.UNSPECIFIED), "project")
    with pytest.raises(ValueError, match="latest"):
        resolve_stack(replace(stack_profile(), language="latest"), "project")


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("project_status", WebLifecycleStatus.ARCHITECTURE_APPROVED, "UI_APPROVED"),
        ("project_id", "different", "identity"),
        ("expected_ui_specification_fingerprint", "0" * 64, "stale"),
    ],
)
def test_prepare_fails_closed_on_stale_authority(
    tmp_path: Path, field: str, value: object, message: str
) -> None:
    with pytest.raises(WorkspacePreparationError, match=message):
        prepare_workspace(
            replace(workspace_command(tmp_path), **{field: value})  # type: ignore[arg-type]
        )


def test_dirty_and_detached_repositories_are_findings(tmp_path: Path) -> None:
    command = workspace_command(tmp_path)
    repository = replace(
        command.baseline.repository, present=True, detached=True, dirty_paths=("user.txt",)
    )
    result = prepare_workspace(
        replace(command, baseline=replace(command.baseline, repository=repository))
    )
    assert result.review.readiness is WorkspaceReadiness.NOT_READY
    assert {item.code for item in result.review.findings} == {
        WorkspaceFindingCode.DETACHED_HEAD,
        WorkspaceFindingCode.DIRTY_REPOSITORY,
    }
    allowed = replace(
        command,
        baseline=replace(command.baseline, repository=repository),
        policy=WorkspaceExecutionPolicy(False, True),
    )
    assert prepare_workspace(allowed).review.readiness is WorkspaceReadiness.READY_FOR_REVIEW


def test_path_claim_overlap_and_dependency_cycles_are_rejected(tmp_path: Path) -> None:
    plan = prepare_workspace(workspace_command(tmp_path)).plan
    left = PathClaim("claim:a", plan.units[0].unit_id, "src/**", PathClaimMode.EXCLUSIVE)
    right = PathClaim("claim:b", plan.units[-1].unit_id, "src/app/**", PathClaimMode.EXCLUSIVE)
    with pytest.raises(ValueError, match="overlap"):
        replace(plan, path_claims=(left, right))
    unit = replace(plan.units[0], dependency_refs=(plan.units[-1].unit_id,))
    other = replace(plan.units[-1], dependency_refs=(unit.unit_id,))
    with pytest.raises(ValueError, match="cycle"):
        ImplementationPlan(
            plan.contract_version,
            plan.plan_id,
            plan.project_id,
            plan.requirements_ref,
            plan.architecture_ref,
            plan.design_system_ref,
            plan.ui_specification_ref,
            plan.ui_review_ref,
            plan.stack_ref,
            (unit, other),
            (),
        )


def test_new_repository_plans_git_init_only(tmp_path: Path) -> None:
    result = prepare_workspace(workspace_command(tmp_path / "new", new=True))
    assert [item.operation.value for item in result.change_set.changes] == ["git_init"]


def test_missing_required_tool_blocks_readiness(tmp_path: Path) -> None:
    command = workspace_command(tmp_path)
    baseline = replace(command.baseline, toolchain_capabilities=())
    result = prepare_workspace(replace(command, baseline=baseline))
    assert result.review.readiness is WorkspaceReadiness.NOT_READY
    assert WorkspaceFindingCode.MISSING_TOOL in {item.code for item in result.review.findings}
