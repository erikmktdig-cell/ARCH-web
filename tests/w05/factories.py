"""W05 factories from exact W04 evidence."""

from __future__ import annotations

from pathlib import Path

from arch_web import (
    ArchitectureChoice,
    PrepareWorkspaceCommand,
    WebLifecycleStatus,
    WebRoute,
    WebStackProfile,
    WorkspaceExecutionPolicy,
    WorkspaceKind,
    WorkspaceTarget,
    prepare_ui_specification,
)
from arch_web.adapters.local.filesystem import LocalFileSystem
from arch_web.adapters.local.git import LocalGit
from arch_web.adapters.local.toolchain import LocalToolchainProbe, ToolProbeSpec
from arch_web.contracts.versions import CURRENT_WEB_CONTRACT_VERSION
from w02.factories import PROJECT_ID
from w04.factories import design_command


def stack_profile() -> WebStackProfile:
    return WebStackProfile(
        CURRENT_WEB_CONTRACT_VERSION,
        "stack:explicit-static",
        "python@3.13",
        ArchitectureChoice.NONE,
        "static",
        ArchitectureChoice.NONE,
        ArchitectureChoice.NONE,
        ArchitectureChoice.NONE,
        ArchitectureChoice.NONE,
        "pytest@8",
        ArchitectureChoice.NONE,
        ArchitectureChoice.NONE,
        "python>=3.12,<3.14",
        ("offline bootstrap",),
    )


def workspace_command(
    root: Path,
    route: WebRoute = WebRoute.QUICK,
    *,
    new: bool = False,
    policy: WorkspaceExecutionPolicy | None = None,
) -> PrepareWorkspaceCommand:
    design_input = design_command(route)
    prepared_ui = prepare_ui_specification(design_input)
    target = WorkspaceTarget(
        "workspace:test",
        PROJECT_ID,
        str(root),
        WorkspaceKind.NEW_REPOSITORY if new else WorkspaceKind.EXISTING_REPOSITORY,
        route,
    )
    capability = LocalToolchainProbe(root.parent).probe(ToolProbeSpec("git", "git"))
    baseline = LocalFileSystem(root, (capability,)).inspect(target, LocalGit(root).inspect())
    return PrepareWorkspaceCommand(
        PROJECT_ID,
        WebLifecycleStatus.UI_APPROVED,
        design_input.requirements,
        design_input.architecture,
        prepared_ui.design_system,
        prepared_ui.ui_specification,
        prepared_ui.review_package,
        stack_profile(),
        target,
        baseline,
        policy or WorkspaceExecutionPolicy(),
        design_input.requirements.canonical_fingerprint(),
        design_input.architecture.canonical_fingerprint(),
        prepared_ui.design_system.canonical_fingerprint(),
        prepared_ui.ui_specification.canonical_fingerprint(),
        prepared_ui.review_package.canonical_fingerprint(),
    )
