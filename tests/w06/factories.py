"""W06 fixtures from exact W04/W05 evidence."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Any

from arch_web import (
    ApplyFrontendUnitCommand,
    ApplyWorkspaceCommand,
    FrontendExecutionAuthorization,
    FrontendImplementationProposal,
    PrepareFrontendCommand,
    StaticFrontendAdapter,
    WebLifecycleStatus,
    WorkspaceExecutionPolicy,
    WorkspaceExecutor,
    prepare_frontend,
    prepare_ui_specification,
    prepare_workspace,
)
from arch_web.adapters.local.filesystem import LocalFileSystem
from arch_web.adapters.local.git import LocalGit
from arch_web.contracts.versions import CURRENT_WEB_CONTRACT_VERSION
from w04.factories import design_command
from w05.factories import workspace_command


def prepared_frontend(root: Path, *, new: bool = False) -> tuple[Any, ...]:
    workspace_source = workspace_command(root, new=new)
    workspace = prepare_workspace(workspace_source)
    receipt = (
        WorkspaceExecutor()
        .apply(
            ApplyWorkspaceCommand(
                "execution:w06-ready",
                workspace_source.target,
                workspace,
                workspace_source.policy,
            )
        )
        .receipt
    )
    current_baseline = LocalFileSystem(root, workspace.baseline.toolchain_capabilities).inspect(
        workspace_source.target, LocalGit(root).inspect()
    )
    design_source = design_command()
    design = prepare_ui_specification(design_source)
    selected = tuple(
        item.unit_id for item in workspace.plan.units if item.kind.value in {"frontend", "shared"}
    )
    command = PrepareFrontendCommand(
        workspace.plan.project_id,
        WebLifecycleStatus.IMPLEMENTATION_READY,
        6,
        "sha256:" + "a" * 64,
        workspace.plan.requirements_ref.fingerprint,
        design_source.architecture,
        design.design_system,
        design.ui_specification,
        design.review_package,
        workspace,
        receipt,
        current_baseline,
        receipt.post_tree_fingerprint,
        receipt.repository_evidence.after_head,
        selected,
    )
    return workspace_source, workspace, receipt, command, prepare_frontend(command)


def proposal_bundle(root: Path, *, new: bool = False) -> tuple[Any, ...]:
    source, workspace, receipt, command, prepared = prepared_frontend(root, new=new)
    adapter = StaticFrontendAdapter()
    proposal = adapter.reference_proposal(
        prepared.assignment,
        command.design_system,
        command.ui_specification,
        workspace.plan,
    )
    authorization = FrontendExecutionAuthorization(
        CURRENT_WEB_CONTRACT_VERSION,
        "FAU-test",
        command.project_id,
        prepared.assignment.canonical_fingerprint(),
        workspace.plan.canonical_fingerprint(),
        receipt.canonical_fingerprint(),
        command.runtime_record_version,
        command.runtime_record_fingerprint,
        True,
    )
    apply = ApplyFrontendUnitCommand(
        "execution:w06-frontend",
        WebLifecycleStatus.IMPLEMENTING,
        prepared.assignment,
        authorization,
        proposal,
        prepared.execution_workspace,
        source.target,
        WorkspaceExecutionPolicy(),
    )
    return source, workspace, command, prepared, adapter, proposal, authorization, apply


def replace_artifact(
    proposal: FrontendImplementationProposal,
    index: int = 0,
    **changes: Any,
) -> FrontendImplementationProposal:
    artifacts = list(proposal.artifacts)
    artifacts[index] = replace(artifacts[index], **changes)
    return replace(proposal, artifacts=tuple(artifacts))
