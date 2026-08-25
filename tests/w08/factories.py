"""Exact W07-to-W08 reference fixture."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Any

from arch_web import (
    BrowserSupportPolicy,
    PrepareQACommand,
    QABaselineProfile,
    VerifyBackendCommand,
    ViewportPolicy,
    ViewportSpec,
    WebLifecycleStatus,
    WebRoute,
    apply_backend_unit,
    prepare_qa,
    prepare_ui_specification,
    verify_backend,
)
from arch_web.adapters.local.filesystem import LocalFileSystem
from arch_web.adapters.local.git import LocalGit
from arch_web.contracts.versions import CURRENT_WEB_CONTRACT_VERSION
from w04.factories import design_command
from w07.factories import backend_bundle


def qa_profile() -> QABaselineProfile:
    return QABaselineProfile(
        CURRENT_WEB_CONTRACT_VERSION,
        "QAP-standard-local",
        route=WebRoute.QUICK,
        browser_policy=BrowserSupportPolicy(
            "browser-local-chromium",
            ("chromium",),
            ("locally-provisioned-system-binary",),
            True,
            False,
        ),
        viewport_policy=ViewportPolicy(
            "viewport-responsive-baseline",
            (
                ViewportSpec("desktop", 1280, 800, False),
                ViewportSpec("mobile", 390, 844, True),
            ),
            (720,),
        ),
        accessibility_policy=("landmark", "keyboard-focus", "not-wcag-certification"),
        runtime_observation_policy=("console-errors", "overflow", "external-network"),
        visual_threshold=None,
        visual_baseline_ref=None,
        performance_budgets=(("interactive_observation_seconds", 5.0),),
        adopted=True,
    )


def qa_bundle(root: Path) -> tuple[Any, ...]:
    source, workspace, frontend, command, prepared_backend, adapter, proposal, apply, _ = (
        backend_bundle(root)
    )
    applied = apply_backend_unit(apply)
    backend = verify_backend(
        VerifyBackendCommand(
            WebLifecycleStatus.IMPLEMENTING,
            prepared_backend.assignment,
            applied,
            workspace,
            frontend,
            ("authorization", "migration", "repository", "security"),
        ),
        adapter,
    ).completion
    git_head = "f" * 40
    assert backend.workspace_receipt is not None
    backend = replace(
        backend,
        workspace_receipt=replace(
            backend.workspace_receipt,
            repository_evidence=replace(
                backend.workspace_receipt.repository_evidence,
                after_head=git_head,
            ),
        ),
    )
    baseline = LocalFileSystem(root, workspace.baseline.toolchain_capabilities).inspect(
        source.target, LocalGit(root).inspect()
    )
    baseline = replace(baseline, repository=replace(baseline.repository, head=git_head))
    design_source = design_command()
    design = prepare_ui_specification(design_source)
    entrypoint = next(
        item.path
        for item in command.frontend_proposal.artifacts
        if item.path.endswith("index.html")
    )
    profile = qa_profile()
    prepare_command = PrepareQACommand(
        command.project_id,
        WebLifecycleStatus.IMPLEMENTING,
        profile.route,
        8,
        "sha256:" + "c" * 64,
        command.requirements_fingerprint,
        command.architecture,
        design.design_system,
        design.ui_specification,
        workspace,
        frontend,
        command.frontend_proposal,
        backend,
        proposal,
        baseline,
        profile,
        tuple(
            item.content_fingerprint
            for item in (*command.frontend_proposal.artifacts, *proposal.artifacts)
        ),
        str(root),
        entrypoint,
        "fixture:w08-reference",
        str(root / "application.sqlite"),
        str(root / "runtime.sqlite"),
    )
    return prepare_command, prepare_qa(prepare_command), profile


def stale_baseline(command: PrepareQACommand) -> PrepareQACommand:
    return replace(
        command,
        current_baseline=replace(command.current_baseline, tree_fingerprint="sha256:stale"),
    )
