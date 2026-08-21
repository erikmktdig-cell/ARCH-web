"""Pure deterministic W05 stack, implementation, and workspace planning."""

from __future__ import annotations

from arch_web.application.architecture.planning import semantic_id
from arch_web.application.workspace.errors import WorkspacePreparationError
from arch_web.application.workspace.models import PrepareWorkspaceCommand, PrepareWorkspaceResult
from arch_web.contracts.versions import CURRENT_WEB_CONTRACT_VERSION
from arch_web.domain._base import WebContractRecord
from arch_web.domain.enums import ArchitectureChoice, WebLifecycleStatus
from arch_web.domain.references import ContractRef
from arch_web.domain.stack import StackValue, WebStackProfile
from arch_web.domain.workspace import (
    ImplementationPlan,
    ImplementationUnit,
    ImplementationUnitKind,
    PathClaim,
    PathClaimMode,
    ResolvedStackManifest,
    WorkspaceChange,
    WorkspaceChangeSet,
    WorkspaceFinding,
    WorkspaceFindingCode,
    WorkspaceKind,
    WorkspaceOperation,
    WorkspaceReadiness,
    WorkspaceReviewPackage,
)


def _text(value: StackValue, field: str) -> str:
    if value is ArchitectureChoice.UNSPECIFIED:
        raise WorkspacePreparationError(f"Stack field {field} is unresolved")
    return value.value if isinstance(value, ArchitectureChoice) else value


def _ref(value: WebContractRecord, identifier: str) -> ContractRef:
    return ContractRef(
        value.contract_type,
        identifier,
        getattr(value, "contract_version", CURRENT_WEB_CONTRACT_VERSION),
        value.canonical_fingerprint(),
    )


def resolve_stack(profile: WebStackProfile, project_id: str) -> ResolvedStackManifest:
    language = _text(profile.language, "language")
    runtime = _text(profile.runtime_requirement, "runtime_requirement")
    package_manager = _text(profile.package_manager, "package_manager")
    required = ["git"]
    if package_manager != ArchitectureChoice.NONE.value:
        required.append(package_manager)
    identity = {"project": project_id, "profile": profile, "required": required}
    return ResolvedStackManifest(
        CURRENT_WEB_CONTRACT_VERSION,
        semantic_id("RSM", identity),
        project_id,
        _ref(profile, profile.profile_id),
        language,
        runtime,
        _text(profile.frontend_framework, "frontend_framework"),
        _text(profile.rendering_mode, "rendering_mode"),
        package_manager,
        _text(profile.backend_model, "backend_model"),
        _text(profile.unit_test_runner, "unit_test_runner"),
        _text(profile.e2e_test_runner, "e2e_test_runner"),
        "required" if package_manager != ArchitectureChoice.NONE.value else "not_applicable",
        tuple(required),
        False,
        profile.constraints,
    )


def _plan(command: PrepareWorkspaceCommand, stack: ResolvedStackManifest) -> ImplementationPlan:
    ui = command.ui_specification
    shared_id = semantic_id("IUN", {"project": command.project_id, "kind": "shared-design"})
    units = [
        ImplementationUnit(
            shared_id,
            ImplementationUnitKind.SHARED,
            "Map approved design semantics into implementation-owned shared foundations.",
            (),
            (),
            (),
            (),
            ("src/shared/design/**",),
            (),
            ("token mapping evidence", "accessibility baseline tests"),
            "design-system implementer",
            "standard",
            ("inventing tokens", "final product behavior"),
        )
    ]
    claims = [
        PathClaim(
            semantic_id("PCL", {"unit": shared_id}),
            shared_id,
            "src/shared/design/**",
            PathClaimMode.EXCLUSIVE,
        )
    ]
    components_by_surface: dict[str, list[str]] = {}
    for component in ui.components:
        for surface_ref in component.surface_refs:
            components_by_surface.setdefault(surface_ref, []).append(component.component_id)
    for surface in ui.surfaces:
        unit_id = semantic_id(
            "IUN", {"project": command.project_id, "surface": surface.surface_ref}
        )
        path = f"src/surfaces/{surface.surface_ref.lower()}/**"
        units.append(
            ImplementationUnit(
                unit_id,
                ImplementationUnitKind.FRONTEND,
                f"Implement the approved interaction contract for surface {surface.surface_ref}.",
                surface.requirement_refs,
                surface.architecture_refs,
                (surface.surface_ref,),
                tuple(components_by_surface.get(surface.surface_ref, ())),
                (path,),
                (shared_id,),
                ("surface behavior tests", "responsive evidence", "accessibility evidence"),
                "frontend implementer",
                "critical" if command.target.route.value == "critical" else "standard",
                ("unapproved routes", "unapproved backend", "deployment"),
            )
        )
        claims.append(
            PathClaim(
                semantic_id("PCL", {"unit": unit_id, "path": path}),
                unit_id,
                path,
                PathClaimMode.EXCLUSIVE,
            )
        )
    identity = {"project": command.project_id, "stack": stack, "units": units, "claims": claims}
    return ImplementationPlan(
        CURRENT_WEB_CONTRACT_VERSION,
        semantic_id("IPL", identity),
        command.project_id,
        _ref(command.requirements, command.requirements.contract_id),
        _ref(command.architecture, command.architecture.contract_id),
        _ref(command.design_system, command.design_system.contract_id),
        _ref(command.ui_specification, command.ui_specification.contract_id),
        _ref(command.ui_review, command.ui_review.review_id),
        _ref(stack, stack.manifest_id),
        tuple(units),
        tuple(claims),
    )


def _validate(command: PrepareWorkspaceCommand) -> None:
    if command.project_status is not WebLifecycleStatus.UI_APPROVED:
        raise WorkspacePreparationError("Workspace preparation requires UI_APPROVED")
    identities = {
        command.project_id,
        command.requirements.project_id,
        command.architecture.project_id,
        command.design_system.project_id,
        command.ui_specification.project_id,
        command.ui_review.project_id,
        command.target.project_id,
        command.baseline.project_id,
    }
    if len(identities) != 1 or command.target.workspace_id != command.baseline.workspace_id:
        raise WorkspacePreparationError("Workspace/project identity mismatch")
    bindings = (
        (command.requirements.canonical_fingerprint(), command.expected_requirements_fingerprint),
        (command.architecture.canonical_fingerprint(), command.expected_architecture_fingerprint),
        (command.design_system.canonical_fingerprint(), command.expected_design_system_fingerprint),
        (
            command.ui_specification.canonical_fingerprint(),
            command.expected_ui_specification_fingerprint,
        ),
        (command.ui_review.canonical_fingerprint(), command.expected_ui_review_fingerprint),
    )
    if any(actual != expected for actual, expected in bindings):
        raise WorkspacePreparationError("Upstream fingerprint is stale")


def prepare_workspace(command: PrepareWorkspaceCommand) -> PrepareWorkspaceResult:
    _validate(command)
    stack = resolve_stack(command.stack_profile, command.project_id)
    plan = _plan(command, stack)
    changes: tuple[WorkspaceChange, ...] = ()
    if (
        command.target.kind is WorkspaceKind.NEW_REPOSITORY
        and not command.baseline.repository.present
    ):
        changes = (
            WorkspaceChange(
                semantic_id("WCH", {"workspace": command.target.workspace_id, "op": "git_init"}),
                WorkspaceOperation.GIT_INIT,
                None,
                None,
                None,
                None,
                plan.units[0].unit_id,
                "Initialize the explicitly approved local repository.",
            ),
        )
    change_set = WorkspaceChangeSet(
        CURRENT_WEB_CONTRACT_VERSION,
        semantic_id(
            "WCS", {"plan": plan, "baseline": command.baseline.tree_fingerprint, "changes": changes}
        ),
        command.project_id,
        command.target.workspace_id,
        plan.canonical_fingerprint(),
        command.baseline.canonical_fingerprint(),
        changes,
    )
    findings: list[WorkspaceFinding] = []
    repo = command.baseline.repository
    if command.policy.require_clean_repository and repo.dirty_paths:
        findings.append(
            WorkspaceFinding(
                semantic_id("WFD", {"code": "dirty", "paths": repo.dirty_paths}),
                WorkspaceFindingCode.DIRTY_REPOSITORY,
                "Repository has unapproved changes.",
                repo.dirty_paths,
            )
        )
    if repo.detached and not command.policy.allow_detached_head:
        findings.append(
            WorkspaceFinding(
                semantic_id("WFD", {"code": "detached"}),
                WorkspaceFindingCode.DETACHED_HEAD,
                "Detached HEAD is not permitted.",
            )
        )
    available_tools = {
        item.tool_id for item in command.baseline.toolchain_capabilities if item.available
    }
    missing_tools = tuple(sorted(set(stack.required_tools) - available_tools))
    if missing_tools:
        findings.append(
            WorkspaceFinding(
                semantic_id("WFD", {"code": "missing-tools", "tools": missing_tools}),
                WorkspaceFindingCode.MISSING_TOOL,
                "Required local tools are unavailable.",
                missing_tools,
            )
        )
    covered_surfaces = {ref for unit in plan.units for ref in unit.surface_refs}
    missing = tuple(
        sorted({item.surface_ref for item in command.ui_specification.surfaces} - covered_surfaces)
    )
    if missing:
        findings.append(
            WorkspaceFinding(
                semantic_id("WFD", {"code": "coverage", "refs": missing}),
                WorkspaceFindingCode.MISSING_IMPLEMENTATION_DISPOSITION,
                "Approved UI surfaces lack implementation disposition.",
                missing,
            )
        )
    review = WorkspaceReviewPackage(
        CURRENT_WEB_CONTRACT_VERSION,
        semantic_id(
            "WRV", {"plan": plan, "stack": stack, "changes": change_set, "findings": findings}
        ),
        command.project_id,
        command.target.route,
        _ref(plan, plan.plan_id),
        _ref(stack, stack.manifest_id),
        _ref(change_set, change_set.change_set_id),
        None,
        tuple(findings),
        WorkspaceReadiness.NOT_READY if findings else WorkspaceReadiness.READY_FOR_REVIEW,
    )
    return PrepareWorkspaceResult(command.baseline, stack, plan, change_set, review)


__all__ = ("prepare_workspace", "resolve_stack")
