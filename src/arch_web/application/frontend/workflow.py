"""Deterministic W06 preparation, validation, execution, and completion."""

from __future__ import annotations

import hashlib
import re
from dataclasses import replace

from arch_web.adapters.local.filesystem import sha256_bytes
from arch_web.application.architecture.planning import semantic_id
from arch_web.application.frontend.errors import (
    FrontendPreparationError,
    FrontendProposalError,
    UnsupportedFrontendStackError,
)
from arch_web.application.frontend.models import (
    ApplyFrontendUnitCommand,
    ApplyFrontendUnitResult,
    PrepareFrontendCommand,
    PrepareFrontendResult,
    VerifyFrontendCommand,
    VerifyFrontendResult,
)
from arch_web.application.workspace.execution import WorkspaceExecutor, dry_run_workspace
from arch_web.application.workspace.models import ApplyWorkspaceCommand
from arch_web.contracts.versions import CURRENT_WEB_CONTRACT_VERSION
from arch_web.domain.enums import WebLifecycleStatus
from arch_web.domain.frontend import (
    FrontendAssignmentPacket,
    FrontendCheckStatus,
    FrontendCompletionPackage,
    FrontendFinding,
    FrontendFindingCode,
    FrontendReadiness,
    FrontendUnitResult,
)
from arch_web.domain.references import ContractRef
from arch_web.domain.workspace import (
    ExecutionOutcome,
    ImplementationUnitKind,
    ReconciliationStatus,
    WorkspaceChange,
    WorkspaceChangeSet,
    WorkspaceOperation,
)
from arch_web.ports.frontend import FrontendStackAdapter
from arch_web.workspace_paths import normalize_managed_path

_SECRET = re.compile(r"(?i)(api[_-]?key|token|password|private[_-]?key)\s*[:=]\s*[^\s;]+")
_UNSAFE = re.compile(
    r"(?i)(dangerouslySetInnerHTML|\beval\s*\(|document\.write\s*\(|<script[^>]+src=https?://)"
)
_TRACKER = re.compile(r"(?i)(google-analytics|googletagmanager|segment\.com|mixpanel)")
_ENDPOINT = re.compile(r"(?i)(fetch\s*\(\s*['\"]https?://|axios\.[a-z]+\s*\(\s*['\"]https?://)")
_RAW_COLOR = re.compile(r"#[0-9A-Fa-f]{6}\b")


def _claim_matches(path: str, pattern: str) -> bool:
    normalized = normalize_managed_path(path)
    root = normalize_managed_path(pattern.removesuffix("/**"))
    return normalized == root or normalized.startswith(root + "/")


def prepare_frontend(command: PrepareFrontendCommand) -> PrepareFrontendResult:
    if command.project_status is not WebLifecycleStatus.IMPLEMENTATION_READY:
        raise FrontendPreparationError("Frontend preparation requires IMPLEMENTATION_READY")
    workspace = command.prepared_workspace
    receipt = command.workspace_receipt
    identities = {
        command.project_id,
        workspace.plan.project_id,
        workspace.stack.project_id,
        receipt.project_id,
        command.current_baseline.project_id,
    }
    if (
        len(identities) != 1
        or command.current_baseline.workspace_id != workspace.baseline.workspace_id
    ):
        raise FrontendPreparationError("Frontend project identity mismatch")
    bindings = (
        (command.requirements_fingerprint, workspace.plan.requirements_ref.fingerprint),
        (command.architecture.canonical_fingerprint(), workspace.plan.architecture_ref.fingerprint),
        (
            command.design_system.canonical_fingerprint(),
            workspace.plan.design_system_ref.fingerprint,
        ),
        (
            command.ui_specification.canonical_fingerprint(),
            workspace.plan.ui_specification_ref.fingerprint,
        ),
        (command.ui_review.canonical_fingerprint(), workspace.plan.ui_review_ref.fingerprint),
        (workspace.stack.canonical_fingerprint(), receipt.resolved_stack_fingerprint),
        (workspace.plan.canonical_fingerprint(), receipt.implementation_plan_fingerprint),
        (workspace.change_set.canonical_fingerprint(), receipt.change_set_fingerprint),
        (receipt.post_tree_fingerprint, command.current_tree_fingerprint),
        (receipt.repository_evidence.after_head, command.current_git_head),
        (command.current_baseline.tree_fingerprint, command.current_tree_fingerprint),
        (command.current_baseline.repository.head, command.current_git_head),
    )
    if any(actual != expected for actual, expected in bindings):
        raise FrontendPreparationError("Frontend assignment evidence is stale")
    if (
        receipt.outcome not in {ExecutionOutcome.APPLIED, ExecutionOutcome.NOOP_ALREADY_SATISFIED}
        or receipt.reconciliation_status is not ReconciliationStatus.CLEAN
    ):
        raise FrontendPreparationError("W05 execution is not clean")
    units = {item.unit_id: item for item in workspace.plan.units}
    selected = tuple(units.get(ref) for ref in command.selected_unit_refs)
    if not selected or any(item is None for item in selected):
        raise FrontendPreparationError("Selected frontend unit is unknown")
    allowed = {
        ImplementationUnitKind.FRONTEND,
        ImplementationUnitKind.SHARED,
        ImplementationUnitKind.CONFIGURATION,
        ImplementationUnitKind.TESTING_SUPPORT,
    }
    if any(item.kind not in allowed for item in selected if item is not None):
        raise FrontendPreparationError("Selected unit is not frontend-authorized")
    selected_ids = {item.unit_id for item in selected if item is not None}
    claims = tuple(item for item in workspace.plan.path_claims if item.unit_ref in selected_ids)
    if not claims:
        raise FrontendPreparationError("Selected frontend units have no path claims")
    surfaces = tuple(
        sorted({ref for item in selected if item is not None for ref in item.surface_refs})
    )
    components = tuple(
        sorted({ref for item in selected if item is not None for ref in item.component_refs})
    )
    route_by_surface = {item.surface_ref: item.route_id for item in command.architecture.routes}
    routes = tuple(sorted({route_by_surface[ref] for ref in surfaces if ref in route_by_surface}))
    route_paths = tuple(
        (item.route_id, item.path_pattern)
        for item in command.architecture.routes
        if item.route_id in routes
    )
    ui_components = {item.component_id: item for item in command.ui_specification.components}
    component_states = tuple(
        f"{ref}:{state.state.value}" for ref in components for state in ui_components[ref].states
    )
    responsive_refs = tuple(
        sorted(
            {
                ref
                for component in command.ui_specification.components
                if component.component_id in components
                for ref in component.responsive_rule_refs
            }
            | {
                ref
                for surface in command.ui_specification.surfaces
                if surface.surface_ref in surfaces
                for ref in surface.responsive_rule_refs
            }
        )
    )
    identity = {
        "project": command.project_id,
        "runtime": command.runtime_record_fingerprint,
        "plan": workspace.plan.canonical_fingerprint(),
        "receipt": receipt.canonical_fingerprint(),
        "units": sorted(selected_ids),
        "tree": command.current_tree_fingerprint,
        "git": command.current_git_head,
    }
    assignment = FrontendAssignmentPacket(
        CURRENT_WEB_CONTRACT_VERSION,
        semantic_id("FAS", identity),
        command.project_id,
        WebLifecycleStatus.IMPLEMENTATION_READY,
        command.runtime_record_version,
        command.runtime_record_fingerprint,
        command.requirements_fingerprint,
        command.architecture.canonical_fingerprint(),
        command.design_system.canonical_fingerprint(),
        command.ui_specification.canonical_fingerprint(),
        command.ui_review.canonical_fingerprint(),
        workspace.stack.canonical_fingerprint(),
        workspace.plan.canonical_fingerprint(),
        receipt.canonical_fingerprint(),
        command.current_tree_fingerprint,
        command.current_git_head,
        tuple(selected_ids),
        tuple(item.claim_id for item in claims),
        surfaces,
        routes,
        route_paths,
        components,
        component_states,
        responsive_refs,
        tuple(item.role for item in command.design_system.semantic_tokens.tokens),
        tuple(
            sorted(
                {
                    evidence
                    for item in selected
                    if item is not None
                    for evidence in item.acceptance_evidence
                }
            )
        ),
        tuple(
            sorted(
                {scope for item in selected if item is not None for scope in item.prohibited_scope}
            )
        ),
        (
            "blocking finding",
            "path claim conflict",
            "reconciliation required",
            "stale evidence",
        ),
    )
    return PrepareFrontendResult(
        assignment,
        replace(workspace, baseline=command.current_baseline),
    )


def _finding(
    code: FrontendFindingCode, message: str, refs: tuple[str, ...] = ()
) -> FrontendFinding:
    return FrontendFinding(
        semantic_id("FFD", {"code": code, "message": message, "refs": refs}),
        code,
        message,
        refs,
    )


def proposal_findings(
    assignment: FrontendAssignmentPacket,
    proposal: object,
    prepared_workspace: object,
) -> tuple[FrontendFinding, ...]:
    from arch_web.application.workspace.models import PrepareWorkspaceResult
    from arch_web.domain.frontend import FrontendImplementationProposal

    assert isinstance(proposal, FrontendImplementationProposal)
    assert isinstance(prepared_workspace, PrepareWorkspaceResult)
    findings = list(proposal.findings)
    known_claims = {
        item.claim_id: item
        for item in prepared_workspace.plan.path_claims
        if item.claim_id in assignment.path_claim_refs
    }
    if proposal.assignment_fingerprint != assignment.canonical_fingerprint() or set(
        proposal.unit_refs
    ) != set(assignment.selected_unit_refs):
        findings.append(
            _finding(
                FrontendFindingCode.STALE_EVIDENCE,
                "Proposal does not bind the exact assignment",
            )
        )
    artifact_ids = {item.artifact_id for item in proposal.artifacts}
    token_artifact_ids = {item.artifact_ref for item in proposal.token_bindings}
    for artifact in proposal.artifacts:
        claim = known_claims.get(artifact.claim_ref)
        if (
            claim is None
            or claim.unit_ref != artifact.unit_ref
            or not _claim_matches(artifact.path, claim.path_pattern)
        ):
            findings.append(
                _finding(
                    FrontendFindingCode.PATH_CLAIM_VIOLATION,
                    "Artifact is outside its approved path claim",
                    (artifact.path,),
                )
            )
        expected = "sha256:" + hashlib.sha256(artifact.content.encode()).hexdigest()
        if artifact.content_fingerprint != expected:
            findings.append(
                _finding(
                    FrontendFindingCode.UNKNOWN_ARTIFACT,
                    "Artifact content fingerprint is invalid",
                    (artifact.artifact_id,),
                )
            )
        scans = (
            (_SECRET, FrontendFindingCode.CLIENT_SECRET, "Potential client secret detected"),
            (_UNSAFE, FrontendFindingCode.UNSAFE_SCRIPT, "Unsafe script pattern detected"),
            (_TRACKER, FrontendFindingCode.HIDDEN_TRACKING, "Unapproved tracking detected"),
            (_ENDPOINT, FrontendFindingCode.INVENTED_BACKEND, "External endpoint invented"),
        )
        for pattern, code, message in scans:
            if pattern.search(artifact.content):
                findings.append(_finding(code, message, (artifact.path,)))
        if "PRODUCTION_MOCK" in artifact.content:
            findings.append(
                _finding(
                    FrontendFindingCode.PRODUCTION_MOCK,
                    "Hidden production mock detected",
                    (artifact.path,),
                )
            )
        if artifact.artifact_id not in token_artifact_ids and _RAW_COLOR.search(artifact.content):
            findings.append(
                _finding(
                    FrontendFindingCode.TOKEN_BYPASS,
                    "Raw color bypasses approved semantic tokens",
                    (artifact.path,),
                )
            )
    for binding in proposal.surface_bindings:
        if (
            binding.surface_ref not in assignment.surface_refs
            or set(binding.artifact_refs) - artifact_ids
        ):
            findings.append(
                _finding(
                    FrontendFindingCode.TRACEABILITY_GAP,
                    "Invalid surface binding",
                    (binding.surface_ref,),
                )
            )
    if set(assignment.surface_refs) - {item.surface_ref for item in proposal.surface_bindings}:
        findings.append(
            _finding(
                FrontendFindingCode.TRACEABILITY_GAP,
                "Required surface is not implemented",
            )
        )
    if set(assignment.route_refs) - {item.route_ref for item in proposal.route_bindings}:
        findings.append(
            _finding(
                FrontendFindingCode.ARCHITECTURE_DRIFT,
                "Required route is not implemented",
            )
        )
    approved_paths = dict(assignment.route_paths)
    if any(approved_paths.get(item.route_ref) != item.path for item in proposal.route_bindings):
        findings.append(
            _finding(
                FrontendFindingCode.ARCHITECTURE_DRIFT,
                "Route path differs from approved architecture",
            )
        )
    if set(assignment.component_refs) - {
        item.component_ref for item in proposal.component_bindings
    }:
        findings.append(
            _finding(
                FrontendFindingCode.DESIGN_DRIFT,
                "Required component is not implemented",
            )
        )
    implemented_states = {
        f"{item.component_ref}:{state}"
        for item in proposal.component_bindings
        for state in item.implemented_states
    }
    if set(assignment.component_state_refs) - implemented_states:
        findings.append(
            _finding(
                FrontendFindingCode.MISSING_STATE,
                "Applicable component state is missing",
            )
        )
    implemented_responsive = {
        ref for item in proposal.component_bindings for ref in item.responsive_rule_refs
    }
    if set(assignment.responsive_rule_refs) - implemented_responsive:
        findings.append(
            _finding(
                FrontendFindingCode.RESPONSIVE_GAP,
                "Approved responsive behavior is missing",
            )
        )
    if any(not item.accessibility_evidence for item in proposal.component_bindings):
        findings.append(
            _finding(
                FrontendFindingCode.ACCESSIBILITY_GAP,
                "Accessibility implementation evidence is missing",
            )
        )
    if set(assignment.semantic_token_refs) - {
        item.semantic_token_ref for item in proposal.token_bindings
    }:
        findings.append(
            _finding(
                FrontendFindingCode.TOKEN_BYPASS,
                "Approved semantic token is not materialized",
            )
        )
    for decision in proposal.dependency_decisions:
        if not decision.approved:
            findings.append(
                _finding(
                    FrontendFindingCode.UNAPPROVED_DEPENDENCY,
                    "Dependency is not approved",
                    (decision.dependency,),
                )
            )
    if any(item.casefold().startswith("behavior-change:") for item in proposal.assumptions):
        findings.append(
            _finding(
                FrontendFindingCode.BEHAVIOR_CHANGING_ASSUMPTION,
                "Executor assumption changes approved behavior",
            )
        )
    return tuple(
        sorted(
            {item.finding_id: item for item in findings}.values(),
            key=lambda item: item.finding_id,
        )
    )


def proposal_to_change_set(
    command: ApplyFrontendUnitCommand,
) -> tuple[WorkspaceChangeSet, tuple[tuple[str, bytes], ...]]:
    if (
        command.project_status is not WebLifecycleStatus.IMPLEMENTING
        or not command.authorization.authorized
    ):
        raise FrontendProposalError(
            "Frontend mutation requires governed IMPLEMENTING authorization"
        )
    if command.authorization.assignment_fingerprint != command.assignment.canonical_fingerprint():
        raise FrontendProposalError("Frontend authorization is stale")
    if (
        command.prepared_workspace.baseline.tree_fingerprint
        != command.assignment.managed_tree_fingerprint
        or command.prepared_workspace.baseline.repository.head != command.assignment.git_head
    ):
        raise FrontendProposalError("Frontend execution workspace is stale")
    if any(
        item.blocking
        for item in proposal_findings(
            command.assignment, command.proposal, command.prepared_workspace
        )
    ):
        raise FrontendProposalError("Frontend proposal contains blocking findings")
    baseline = {item.path: item for item in command.prepared_workspace.baseline.files}
    changes: list[WorkspaceChange] = []
    contents: list[tuple[str, bytes]] = []
    for artifact in command.proposal.artifacts:
        path = normalize_managed_path(artifact.path)
        content = artifact.content.encode()
        old = baseline.get(path)
        operation = (
            WorkspaceOperation.CREATE_FILE if old is None else WorkspaceOperation.UPDATE_FILE
        )
        changes.append(
            WorkspaceChange(
                artifact.artifact_id,
                operation,
                path,
                sha256_bytes(content),
                None if old is None else old.fingerprint,
                artifact.claim_ref,
                artifact.unit_ref,
                "Apply validated frontend proposal artifact.",
            )
        )
        contents.append((path, content))
    change_set = WorkspaceChangeSet(
        CURRENT_WEB_CONTRACT_VERSION,
        semantic_id("WCS", {"assignment": command.assignment, "proposal": command.proposal}),
        command.assignment.project_id,
        command.prepared_workspace.change_set.workspace_id,
        command.assignment.implementation_plan_fingerprint,
        command.prepared_workspace.baseline.canonical_fingerprint(),
        tuple(changes),
    )
    return change_set, tuple(sorted(contents))


def apply_frontend_unit(
    command: ApplyFrontendUnitCommand, *, executor: WorkspaceExecutor | None = None
) -> ApplyFrontendUnitResult:
    change_set, contents = proposal_to_change_set(command)
    prepared = replace(command.prepared_workspace, change_set=change_set)
    workspace_command = ApplyWorkspaceCommand(
        command.execution_id,
        command.target,
        prepared,
        command.policy,
        contents,
    )
    if dry_run_workspace(workspace_command).policy_violations:
        raise FrontendProposalError("Frontend change set fails W05 dry-run")
    applied = (executor or WorkspaceExecutor()).apply(workspace_command)
    return ApplyFrontendUnitResult(command.proposal, applied.receipt)


def verify_frontend(
    command: VerifyFrontendCommand, adapter: FrontendStackAdapter
) -> VerifyFrontendResult:
    if command.project_status is not WebLifecycleStatus.IMPLEMENTING:
        raise FrontendProposalError("Frontend verification requires IMPLEMENTING")
    if not adapter.supports(command.prepared_workspace.stack):
        raise UnsupportedFrontendStackError("Resolved W05 stack is unsupported")
    receipt = command.applied.receipt
    checks = adapter.verify(command.applied.proposal, receipt.post_tree_fingerprint)
    findings = list(
        proposal_findings(
            command.assignment,
            command.applied.proposal,
            command.prepared_workspace,
        )
    )
    accepted = {FrontendCheckStatus.PASS, FrontendCheckStatus.NOT_APPLICABLE}
    present = {item.kind for item in checks if item.status in accepted}
    for missing in sorted(set(command.required_check_kinds) - present):
        findings.append(
            _finding(
                FrontendFindingCode.MISSING_CHECK,
                f"Required engineering check is missing: {missing}",
                (missing,),
            )
        )
    for check in checks:
        if check.source_tree_fingerprint != receipt.post_tree_fingerprint or check.status in {
            FrontendCheckStatus.FAIL,
            FrontendCheckStatus.INCONCLUSIVE,
        }:
            findings.append(
                _finding(
                    FrontendFindingCode.CHECK_FAILED,
                    f"Engineering check did not pass: {check.kind}",
                    (check.check_id,),
                )
            )
    if receipt.reconciliation_status is ReconciliationStatus.REQUIRED:
        findings.append(
            _finding(
                FrontendFindingCode.RECONCILIATION_REQUIRED,
                "Workspace reconciliation is required",
            )
        )
    unit_results = tuple(
        FrontendUnitResult(
            unit,
            bool(
                refs := tuple(
                    item.artifact_id
                    for item in command.applied.proposal.artifacts
                    if item.unit_ref == unit
                )
            ),
            refs,
        )
        for unit in command.assignment.selected_unit_refs
    )
    blocked = (
        any(item.blocking for item in findings)
        or receipt.outcome
        not in {ExecutionOutcome.APPLIED, ExecutionOutcome.NOOP_ALREADY_SATISFIED}
        or any(not item.completed for item in unit_results)
    )
    authorization_ref = ContractRef(
        command.authorization.contract_type,
        command.authorization.authorization_id,
        command.authorization.contract_version,
        command.authorization.canonical_fingerprint(),
    )
    completion = FrontendCompletionPackage(
        CURRENT_WEB_CONTRACT_VERSION,
        semantic_id(
            "FCP",
            {
                "assignment": command.assignment,
                "proposal": command.applied.proposal,
                "receipt": receipt,
                "checks": checks,
                "findings": findings,
            },
        ),
        command.assignment.project_id,
        WebLifecycleStatus.IMPLEMENTING,
        authorization_ref,
        command.assignment.implementation_plan_fingerprint,
        command.applied.proposal.canonical_fingerprint(),
        receipt.change_set_fingerprint,
        receipt,
        command.assignment.managed_tree_fingerprint,
        receipt.post_tree_fingerprint,
        adapter.identity,
        unit_results,
        checks,
        tuple(findings),
        receipt.reconciliation_status,
        tuple(
            item.boundary_name
            for item in command.applied.proposal.data_bindings
            if item.boundary_name is not None
            and item.disposition.value == "pending_backend_binding"
        ),
        FrontendReadiness.BLOCKED if blocked else FrontendReadiness.COMPLETE_FOR_REVIEW,
    )
    return VerifyFrontendResult(completion)


__all__ = (
    "apply_frontend_unit",
    "prepare_frontend",
    "proposal_findings",
    "proposal_to_change_set",
    "verify_frontend",
)
