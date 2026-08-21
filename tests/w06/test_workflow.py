"""W06 deterministic preparation, proposal, and completion tests."""

from __future__ import annotations

import hashlib
from dataclasses import replace
from pathlib import Path

import pytest

from arch_web import (
    FrontendCheckStatus,
    FrontendDependencyDecision,
    FrontendEngineeringCheck,
    FrontendFindingCode,
    FrontendPreparationError,
    FrontendProposalError,
    FrontendReadiness,
    ReconciliationStatus,
    UnsupportedFrontendStackError,
    VerifyFrontendCommand,
    WebLifecycleStatus,
    WorkspaceExecutor,
    apply_frontend_unit,
    prepare_frontend,
    proposal_findings,
    proposal_to_change_set,
    verify_frontend,
)
from w06.factories import prepared_frontend, proposal_bundle, replace_artifact


def test_assignment_is_deterministic_and_order_invariant(tmp_path: Path) -> None:
    *_, command, result = prepared_frontend(tmp_path)
    reordered = replace(command, selected_unit_refs=tuple(reversed(command.selected_unit_refs)))
    assert prepare_frontend(reordered) == result
    assert result.assignment.selected_unit_refs == tuple(sorted(command.selected_unit_refs))


@pytest.mark.parametrize(
    ("change", "message"),
    [
        ({"project_status": WebLifecycleStatus.UI_APPROVED}, "IMPLEMENTATION_READY"),
        ({"project_id": "different"}, "identity"),
        ({"requirements_fingerprint": "stale"}, "stale"),
        ({"current_tree_fingerprint": "stale"}, "stale"),
        ({"selected_unit_refs": ("missing",)}, "unknown"),
    ],
)
def test_assignment_rejects_invalid_authority(
    tmp_path: Path, change: dict[str, object], message: str
) -> None:
    *_, command, _ = prepared_frontend(tmp_path)
    with pytest.raises(FrontendPreparationError, match=message):
        prepare_frontend(replace(command, **change))


def test_static_adapter_compiles_primitive_and_semantic_tokens(tmp_path: Path) -> None:
    _, _, command, _, adapter, proposal, _, _ = proposal_bundle(tmp_path)
    css, bindings = adapter.compile_tokens(command.design_system)
    assert "--primitive-color-action" in css
    assert "--action-primary-background: var(--primitive-color-action)" in css
    assert tuple(item.semantic_token_ref for item in proposal.token_bindings) == tuple(
        role for role, _, _ in bindings
    )
    assert adapter.compile_tokens(command.design_system) == (css, bindings)


def test_reference_proposal_preserves_states_responsive_and_accessibility(
    tmp_path: Path,
) -> None:
    _, _, _, prepared, _, proposal, _, _ = proposal_bundle(tmp_path)
    assert {item.surface_ref for item in proposal.surface_bindings} == set(
        prepared.assignment.surface_refs
    )
    assert {item.component_ref for item in proposal.component_bindings} == set(
        prepared.assignment.component_refs
    )
    source = "\n".join(item.content for item in proposal.artifacts)
    assert "@media (max-width: 720px)" in source
    assert "prefers-reduced-motion" in source
    assert "aria-live" in source
    assert "focus-visible" in source
    assert 'data-state="loading"' in source
    assert 'data-state="empty"' in source
    assert 'data-state="error"' in source


@pytest.mark.parametrize(
    ("content", "code"),
    [
        ("api_key=actual-secret", FrontendFindingCode.CLIENT_SECRET),
        ("eval('unsafe')", FrontendFindingCode.UNSAFE_SCRIPT),
        ("google-analytics", FrontendFindingCode.HIDDEN_TRACKING),
        ("fetch('https://invented.example')", FrontendFindingCode.INVENTED_BACKEND),
        ("PRODUCTION_MOCK", FrontendFindingCode.PRODUCTION_MOCK),
    ],
)
def test_security_and_data_scans_block(
    tmp_path: Path, content: str, code: FrontendFindingCode
) -> None:
    _, workspace, _, prepared, _, proposal, _, _ = proposal_bundle(tmp_path)
    changed = replace_artifact(
        proposal,
        content=content,
        content_fingerprint="sha256:" + hashlib.sha256(content.encode()).hexdigest(),
    )
    findings = proposal_findings(prepared.assignment, changed, workspace)
    assert code in {item.code for item in findings}


def test_path_claim_and_fingerprint_violations_block(tmp_path: Path) -> None:
    _, workspace, _, prepared, _, proposal, _, _ = proposal_bundle(tmp_path)
    escaped = replace_artifact(proposal, path="outside/index.html")
    assert FrontendFindingCode.PATH_CLAIM_VIOLATION in {
        item.code for item in proposal_findings(prepared.assignment, escaped, workspace)
    }
    stale = replace_artifact(proposal, content_fingerprint="sha256:" + "0" * 64)
    assert FrontendFindingCode.UNKNOWN_ARTIFACT in {
        item.code for item in proposal_findings(prepared.assignment, stale, workspace)
    }


@pytest.mark.parametrize(
    ("mutation", "code"),
    [
        ("surface", FrontendFindingCode.TRACEABILITY_GAP),
        ("route", FrontendFindingCode.ARCHITECTURE_DRIFT),
        ("route_path", FrontendFindingCode.ARCHITECTURE_DRIFT),
        ("component", FrontendFindingCode.DESIGN_DRIFT),
        ("state", FrontendFindingCode.MISSING_STATE),
        ("responsive", FrontendFindingCode.RESPONSIVE_GAP),
        ("accessibility", FrontendFindingCode.ACCESSIBILITY_GAP),
        ("token", FrontendFindingCode.TOKEN_BYPASS),
        ("dependency", FrontendFindingCode.UNAPPROVED_DEPENDENCY),
        ("assumption", FrontendFindingCode.BEHAVIOR_CHANGING_ASSUMPTION),
    ],
)
def test_traceability_and_governance_gaps_are_explicit(
    tmp_path: Path, mutation: str, code: FrontendFindingCode
) -> None:
    _, workspace, _, prepared, _, proposal, _, _ = proposal_bundle(tmp_path)
    if mutation == "surface":
        changed = replace(proposal, surface_bindings=())
    elif mutation == "route":
        changed = replace(proposal, route_bindings=())
    elif mutation == "route_path":
        route = replace(proposal.route_bindings[0], path="/invented")
        changed = replace(proposal, route_bindings=(route,))
    elif mutation == "component":
        changed = replace(proposal, component_bindings=())
    elif mutation == "responsive":
        changed = replace(
            proposal,
            component_bindings=tuple(
                replace(item, responsive_rule_refs=()) for item in proposal.component_bindings
            ),
        )
    elif mutation in {"state", "accessibility"}:
        component = proposal.component_bindings[0]
        field = {
            "state": "implemented_states",
            "accessibility": "accessibility_evidence",
        }[mutation]
        component = replace(component, **{field: ()})
        changed = replace(
            proposal,
            component_bindings=(component, *proposal.component_bindings[1:]),
        )
    elif mutation == "token":
        changed = replace(proposal, token_bindings=proposal.token_bindings[1:])
    elif mutation == "dependency":
        changed = replace(
            proposal,
            dependency_decisions=(
                FrontendDependencyDecision("library", "1.0.0", False, "not approved"),
            ),
        )
    else:
        changed = replace(proposal, assumptions=("behavior-change: add a new workflow",))
    assert code in {
        item.code for item in proposal_findings(prepared.assignment, changed, workspace)
    }


def test_raw_color_outside_token_artifact_is_blocked(tmp_path: Path) -> None:
    _, workspace, _, prepared, _, proposal, _, _ = proposal_bundle(tmp_path)
    index = next(
        index
        for index, item in enumerate(proposal.artifacts)
        if item.artifact_id not in {binding.artifact_ref for binding in proposal.token_bindings}
    )
    artifact = proposal.artifacts[index]
    content = artifact.content + "\n<!-- #ABCDEF -->\n"
    changed = replace_artifact(
        proposal,
        index,
        content=content,
        content_fingerprint="sha256:" + hashlib.sha256(content.encode()).hexdigest(),
    )
    assert FrontendFindingCode.TOKEN_BYPASS in {
        item.code for item in proposal_findings(prepared.assignment, changed, workspace)
    }


def test_fixed_proposal_derives_exact_w05_change_set(tmp_path: Path) -> None:
    *_, apply = proposal_bundle(tmp_path)
    first = proposal_to_change_set(apply)
    second = proposal_to_change_set(apply)
    assert first == second
    assert {item.path for item in first[0].changes} == {
        item.path for item in apply.proposal.artifacts
    }
    assert not any(path.is_file() for path in tmp_path.rglob("*"))


def test_real_workspace_vertical_slice_and_completion(tmp_path: Path) -> None:
    _, workspace, _, prepared, adapter, proposal, authorization, apply = proposal_bundle(tmp_path)
    applied = apply_frontend_unit(apply)
    assert all((tmp_path / item.path).is_file() for item in proposal.artifacts)
    required = (
        "build",
        "format",
        "lint",
        "route",
        "static_accessibility",
        "traceability",
        "typecheck",
        "unit",
    )
    verified = verify_frontend(
        VerifyFrontendCommand(
            WebLifecycleStatus.IMPLEMENTING,
            prepared.assignment,
            authorization,
            applied,
            workspace,
            required,
        ),
        adapter,
    )
    assert verified.completion.readiness is FrontendReadiness.COMPLETE_FOR_REVIEW
    assert verified.completion.runtime_state is WebLifecycleStatus.IMPLEMENTING
    assert verified.completion.reconciliation_status is ReconciliationStatus.CLEAN
    assert not verified.completion.findings


def test_vertical_slice_uses_post_bootstrap_git_baseline(tmp_path: Path) -> None:
    *_, apply = proposal_bundle(tmp_path, new=True)
    assert apply.prepared_workspace.baseline.repository.present
    result = apply_frontend_unit(apply)
    assert result.receipt.reconciliation_status is ReconciliationStatus.CLEAN


def test_blocking_proposal_never_reaches_w05(tmp_path: Path) -> None:
    *_, apply = proposal_bundle(tmp_path)
    bad = replace(apply, proposal=replace_artifact(apply.proposal, path="server/api.py"))
    with pytest.raises(FrontendProposalError, match="blocking"):
        apply_frontend_unit(bad)
    assert not any(path.is_file() for path in tmp_path.rglob("*"))


def test_w05_dry_run_still_blocks_secret_paths(tmp_path: Path) -> None:
    *_, apply = proposal_bundle(tmp_path)
    artifact = apply.proposal.artifacts[0]
    root = artifact.path.rsplit("/", 1)[0]
    changed = replace_artifact(apply.proposal, path=f"{root}/.env")
    with pytest.raises(FrontendProposalError, match="dry-run"):
        apply_frontend_unit(replace(apply, proposal=changed))


def test_exact_execution_retry_returns_same_receipt(tmp_path: Path) -> None:
    *_, apply = proposal_bundle(tmp_path)
    executor = WorkspaceExecutor()
    first = apply_frontend_unit(apply, executor=executor)
    second = apply_frontend_unit(apply, executor=executor)
    assert first == second


class MissingChecksAdapter:
    identity = "test.missing@1"

    def supports(self, stack: object) -> bool:
        return True

    def verify(self, proposal: object, tree: str) -> tuple[FrontendEngineeringCheck, ...]:
        return (
            FrontendEngineeringCheck(
                "check:lint",
                "lint",
                self.identity,
                "1",
                tree,
                FrontendCheckStatus.INCONCLUSIVE,
                None,
                "sha256:" + "0" * 64,
            ),
        )


def test_missing_or_inconclusive_check_blocks_completion(tmp_path: Path) -> None:
    _, workspace, _, prepared, _, _, authorization, apply = proposal_bundle(tmp_path)
    applied = apply_frontend_unit(apply)
    result = verify_frontend(
        VerifyFrontendCommand(
            WebLifecycleStatus.IMPLEMENTING,
            prepared.assignment,
            authorization,
            applied,
            workspace,
            ("build", "lint"),
        ),
        MissingChecksAdapter(),  # type: ignore[arg-type]
    )
    assert result.completion.readiness is FrontendReadiness.BLOCKED
    assert {item.code for item in result.completion.findings} == {
        FrontendFindingCode.CHECK_FAILED,
        FrontendFindingCode.MISSING_CHECK,
    }


def test_verification_rejects_wrong_state_and_unsupported_stack(tmp_path: Path) -> None:
    _, workspace, _, prepared, adapter, _, authorization, apply = proposal_bundle(tmp_path)
    applied = apply_frontend_unit(apply)
    command = VerifyFrontendCommand(
        WebLifecycleStatus.IMPLEMENTING,
        prepared.assignment,
        authorization,
        applied,
        workspace,
        (),
    )
    with pytest.raises(FrontendProposalError, match="IMPLEMENTING"):
        verify_frontend(replace(command, project_status=WebLifecycleStatus.TESTING), adapter)
    unsupported = replace(workspace.stack, frontend_framework="react@19.1.0")
    with pytest.raises(UnsupportedFrontendStackError, match="unsupported"):
        verify_frontend(
            replace(command, prepared_workspace=replace(workspace, stack=unsupported)),
            adapter,
        )


def test_wrong_lifecycle_or_stale_authorization_never_mutates(tmp_path: Path) -> None:
    *_, apply = proposal_bundle(tmp_path)
    with pytest.raises(FrontendProposalError, match="authorization"):
        proposal_to_change_set(
            replace(apply, project_status=WebLifecycleStatus.IMPLEMENTATION_READY)
        )
    stale = replace(
        apply.authorization,
        assignment_fingerprint="sha256:" + "0" * 64,
    )
    with pytest.raises(FrontendProposalError, match="stale"):
        proposal_to_change_set(replace(apply, authorization=stale))
    stale_workspace = replace(
        apply.prepared_workspace,
        baseline=replace(apply.prepared_workspace.baseline, tree_fingerprint="stale"),
    )
    with pytest.raises(FrontendProposalError, match="workspace"):
        proposal_to_change_set(replace(apply, prepared_workspace=stale_workspace))
