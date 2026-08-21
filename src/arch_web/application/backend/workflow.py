"""Deterministic W07 preparation, execution, and completion."""

from __future__ import annotations

import hashlib
import re
from dataclasses import replace

from arch_web.adapters.local.filesystem import sha256_bytes
from arch_web.application.architecture.planning import semantic_id
from arch_web.application.backend.errors import (
    BackendPreparationError,
    BackendProposalError,
    UnsupportedBackendStackError,
)
from arch_web.application.backend.models import (
    ApplyBackendUnitCommand,
    ApplyBackendUnitResult,
    PrepareBackendCommand,
    PrepareBackendResult,
    VerifyBackendCommand,
    VerifyBackendResult,
)
from arch_web.application.workspace.execution import WorkspaceExecutor, dry_run_workspace
from arch_web.application.workspace.models import ApplyWorkspaceCommand, PrepareWorkspaceResult
from arch_web.contracts.versions import CURRENT_WEB_CONTRACT_VERSION
from arch_web.domain.backend import (
    BackendAssignmentPacket,
    BackendCompletionPackage,
    BackendDisposition,
    BackendFinding,
    BackendFindingCode,
    BackendImplementationProposal,
    BackendUnitResult,
    BindingClosureStatus,
)
from arch_web.domain.enums import WebLifecycleStatus
from arch_web.domain.frontend import FrontendCheckStatus, FrontendReadiness
from arch_web.domain.references import ContractRef
from arch_web.domain.workspace import (
    ExecutionOutcome,
    ImplementationUnitKind,
    ReconciliationStatus,
    WorkspaceChange,
    WorkspaceChangeSet,
    WorkspaceOperation,
)
from arch_web.ports.backend import BackendStackAdapter
from arch_web.workspace_paths import normalize_managed_path

_SECRET = re.compile(
    r"(?i)(api[_-]?key|password|private[_-]?key|client[_-]?secret)\s*[:=]\s*['\"]?(?!\$\{|os\.environ|env\[|SECRET_REF)[^\s'\"]+"
)
_SQL_INJECTION = re.compile(
    r"(?i)(execute\s*\(\s*f['\"]|execute\s*\([^,]+\.format\(|execute\s*\([^,]+\+)"
)
_COMMAND = re.compile(r"(?i)(\beval\s*\(|\bexec\s*\(|shell\s*=\s*True|os\.system\s*\()")
_NETWORK = re.compile(r"(?i)(https?://|requests\.|httpx\.|urllib\.request)")
_RUNTIME = re.compile(
    r"(?i)(arch_runtime|runtime_(projects|events|snapshots)|event_store|snapshot_store)"
)
_SENSITIVE_LOG = re.compile(
    r"(?i)(print|log(?:ger)?\.[a-z]+)\s*\([^\n]*(password|token|secret|personal|payload)"
)


def _claim_matches(path: str, pattern: str) -> bool:
    normalized = normalize_managed_path(path)
    root = normalize_managed_path(pattern.removesuffix("/**"))
    return normalized == root or normalized.startswith(root + "/")


def _finding(code: BackendFindingCode, message: str, refs: tuple[str, ...] = ()) -> BackendFinding:
    return BackendFinding(
        semantic_id("BFD", {"code": code, "message": message, "refs": refs}), code, message, refs
    )


def _contract_values(command: PrepareBackendCommand) -> tuple[object | None, ...]:
    return (
        command.interface,
        command.data_contract,
        command.authentication,
        *command.authorization_rules,
        command.persistence,
        command.migrations,
        *command.integrations,
    )


def prepare_backend(command: PrepareBackendCommand) -> PrepareBackendResult:
    if command.project_status is not WebLifecycleStatus.IMPLEMENTING:
        raise BackendPreparationError("Backend preparation requires IMPLEMENTING")
    workspace = command.prepared_workspace
    completion = command.frontend_completion
    proposal = command.frontend_proposal
    identities = {
        command.project_id,
        workspace.plan.project_id,
        workspace.stack.project_id,
        command.current_baseline.project_id,
        completion.project_id,
    }
    if (
        len(identities) != 1
        or command.current_baseline.workspace_id != workspace.baseline.workspace_id
    ):
        raise BackendPreparationError("Backend project identity mismatch")
    bindings = (
        (command.requirements_fingerprint, workspace.plan.requirements_ref.fingerprint),
        (command.architecture.canonical_fingerprint(), workspace.plan.architecture_ref.fingerprint),
        (workspace.plan.canonical_fingerprint(), completion.implementation_plan_fingerprint),
        (proposal.canonical_fingerprint(), completion.proposal_fingerprint),
        (completion.post_tree_fingerprint, command.current_baseline.tree_fingerprint),
        (
            completion.receipt.repository_evidence.after_head,
            command.current_baseline.repository.head,
        ),
    )
    if any(actual != expected for actual, expected in bindings):
        raise BackendPreparationError("Backend assignment evidence is stale")
    if completion.reconciliation_status is ReconciliationStatus.REQUIRED:
        raise BackendPreparationError("W06 requires reconciliation")
    if completion.readiness is FrontendReadiness.BLOCKED or completion.findings:
        raise BackendPreparationError("W06 has blocking frontend findings")
    units = {item.unit_id: item for item in workspace.plan.units}
    selected = tuple(units.get(ref) for ref in command.selected_unit_refs)
    if any(item is None for item in selected):
        raise BackendPreparationError("Selected backend unit is unknown")
    allowed = {
        ImplementationUnitKind.BACKEND,
        ImplementationUnitKind.SHARED,
        ImplementationUnitKind.CONFIGURATION,
        ImplementationUnitKind.TESTING_SUPPORT,
    }
    if any(item.kind not in allowed for item in selected if item is not None):
        raise BackendPreparationError("Selected unit is not backend-authorized")
    selected_ids = {item.unit_id for item in selected if item is not None}
    claims = tuple(item for item in workspace.plan.path_claims if item.unit_ref in selected_ids)
    pending = completion.w07_handoff
    is_na = not selected_ids and not pending
    values = _contract_values(command)
    if is_na and any(value is not None and value != () for value in values):
        raise BackendPreparationError("Static backend N/A cannot contain invented contracts")
    if not is_na and (
        not selected_ids
        or any(
            value is None
            for value in (
                command.interface,
                command.data_contract,
                command.authentication,
                command.persistence,
                command.migrations,
            )
        )
    ):
        raise BackendPreparationError(
            "Applicable backend requires units and complete approved contracts"
        )
    fingerprints = tuple(
        value.canonical_fingerprint() for value in values if hasattr(value, "canonical_fingerprint")
    )
    assignment = BackendAssignmentPacket(
        CURRENT_WEB_CONTRACT_VERSION,
        semantic_id(
            "BAS",
            {
                "project": command.project_id,
                "runtime": command.runtime_record_fingerprint,
                "plan": workspace.plan,
                "frontend": completion,
                "units": sorted(selected_ids),
                "contracts": fingerprints,
            },
        ),
        command.project_id,
        WebLifecycleStatus.IMPLEMENTING,
        command.runtime_record_version,
        command.runtime_record_fingerprint,
        command.requirements_fingerprint,
        command.architecture.canonical_fingerprint(),
        workspace.plan.canonical_fingerprint(),
        completion.canonical_fingerprint(),
        proposal.canonical_fingerprint(),
        workspace.stack.canonical_fingerprint(),
        command.current_baseline.tree_fingerprint,
        command.current_baseline.repository.head,
        tuple(selected_ids),
        tuple(item.claim_id for item in claims),
        pending,
        fingerprints,
        tuple(
            sorted(
                {scope for item in selected if item is not None for scope in item.prohibited_scope}
                | {"W08 testing/QA", "W09 deployment/release", "ARCH Runtime persistence"}
            )
        ),
    )
    na_completion = None
    if is_na:
        frontend_ref = ContractRef(
            completion.contract_type,
            completion.completion_id,
            completion.contract_version,
            completion.canonical_fingerprint(),
        )
        na_completion = BackendCompletionPackage(
            CURRENT_WEB_CONTRACT_VERSION,
            semantic_id("BCP", {"assignment": assignment, "disposition": "not_applicable"}),
            command.project_id,
            WebLifecycleStatus.IMPLEMENTING,
            BackendDisposition.NOT_APPLICABLE,
            assignment.canonical_fingerprint(),
            None,
            frontend_ref,
            (),
            (),
            None,
            None,
            None,
            None,
            None,
            command.current_baseline.tree_fingerprint,
            command.current_baseline.tree_fingerprint,
            (),
            (),
            ReconciliationStatus.CLEAN,
            ("backend:not_applicable",),
        )
    return PrepareBackendResult(
        assignment, replace(workspace, baseline=command.current_baseline), na_completion
    )


def proposal_findings(
    assignment: BackendAssignmentPacket,
    proposal: BackendImplementationProposal,
    prepared_workspace: PrepareWorkspaceResult,
) -> tuple[BackendFinding, ...]:
    findings = list(proposal.findings)
    claims = {
        item.claim_id: item
        for item in prepared_workspace.plan.path_claims
        if item.claim_id in assignment.path_claim_refs
    }
    if proposal.assignment_fingerprint != assignment.canonical_fingerprint() or set(
        proposal.unit_refs
    ) != set(assignment.selected_unit_refs):
        findings.append(
            _finding(
                BackendFindingCode.STALE_EVIDENCE, "Proposal does not bind the exact assignment"
            )
        )
    approved = {
        proposal.interface.canonical_fingerprint(),
        proposal.data_contract.canonical_fingerprint(),
        proposal.authentication.canonical_fingerprint(),
        proposal.persistence.canonical_fingerprint(),
        proposal.migrations.canonical_fingerprint(),
        *(item.canonical_fingerprint() for item in proposal.authorization_rules),
        *(item.canonical_fingerprint() for item in proposal.integrations),
    }
    if approved != set(assignment.approved_contract_fingerprints):
        findings.append(
            _finding(
                BackendFindingCode.INVENTED_SEMANTICS,
                "Proposal contracts differ from approved evidence",
            )
        )
    for artifact in proposal.artifacts:
        claim = claims.get(artifact.claim_ref)
        if (
            claim is None
            or claim.unit_ref != artifact.unit_ref
            or not _claim_matches(artifact.path, claim.path_pattern)
        ):
            findings.append(
                _finding(
                    BackendFindingCode.PATH_CLAIM_VIOLATION,
                    "Artifact is outside its approved path claim",
                    (artifact.path,),
                )
            )
        expected = "sha256:" + hashlib.sha256(artifact.content.encode()).hexdigest()
        if artifact.content_fingerprint != expected:
            findings.append(
                _finding(
                    BackendFindingCode.STALE_EVIDENCE,
                    "Artifact fingerprint is invalid",
                    (artifact.path,),
                )
            )
        scans = (
            (_SECRET, BackendFindingCode.SECRET_EXPOSURE),
            (_SQL_INJECTION, BackendFindingCode.INJECTION_RISK),
            (_COMMAND, BackendFindingCode.INJECTION_RISK),
            (_NETWORK, BackendFindingCode.HIDDEN_NETWORK),
            (_RUNTIME, BackendFindingCode.RUNTIME_PERSISTENCE_COUPLING),
            (_SENSITIVE_LOG, BackendFindingCode.SENSITIVE_LOGGING),
        )
        for pattern, code in scans:
            if pattern.search(artifact.content):
                findings.append(
                    _finding(
                        code, f"Unsafe backend source detected: {code.value}", (artifact.path,)
                    )
                )
    operations = {item.operation_id: item for item in proposal.interface.operations}
    closure = {item.frontend_binding_ref: item for item in proposal.bindings}
    if set(assignment.pending_frontend_bindings) != set(closure):
        findings.append(
            _finding(
                BackendFindingCode.UNCLOSED_BINDING,
                "Every W06 backend binding requires an explicit disposition",
            )
        )
    for item in closure.values():
        if item.status is BindingClosureStatus.IMPLEMENTED and item.operation_ref not in operations:
            findings.append(
                _finding(
                    BackendFindingCode.FRONTEND_BACKEND_MISMATCH,
                    "Binding refers to an unknown operation",
                    (item.frontend_binding_ref,),
                )
            )
        if item.status is BindingClosureStatus.BLOCKED:
            findings.append(
                _finding(
                    BackendFindingCode.UNCLOSED_BINDING,
                    "Backend binding is blocked",
                    (item.frontend_binding_ref,),
                )
            )
    rules = {item.rule_id: item for item in proposal.authorization_rules}
    for operation in operations.values():
        if (
            operation.authorization_rule_ref is not None
            and operation.authorization_rule_ref not in rules
        ):
            findings.append(
                _finding(
                    BackendFindingCode.MISSING_AUTHORIZATION,
                    "Operation lacks an approved server authorization rule",
                    (operation.operation_id,),
                )
            )
    if (
        proposal.persistence.application_store_ref.casefold()
        == proposal.persistence.runtime_store_ref.casefold()
        or proposal.migrations.application_store_ref != proposal.persistence.application_store_ref
    ):
        findings.append(
            _finding(
                BackendFindingCode.RUNTIME_PERSISTENCE_COUPLING,
                "Application and Runtime persistence must remain separate",
            )
        )
    return tuple(
        sorted(
            {item.finding_id: item for item in findings}.values(), key=lambda item: item.finding_id
        )
    )


def proposal_to_change_set(
    command: ApplyBackendUnitCommand,
) -> tuple[WorkspaceChangeSet, tuple[tuple[str, bytes], ...]]:
    if command.project_status is not WebLifecycleStatus.IMPLEMENTING:
        raise BackendProposalError("Backend mutation requires IMPLEMENTING")
    if (
        command.prepared_workspace.baseline.tree_fingerprint
        != command.assignment.managed_tree_fingerprint
        or command.prepared_workspace.baseline.repository.head != command.assignment.git_head
    ):
        raise BackendProposalError("Backend execution workspace is stale")
    if any(
        item.blocking
        for item in proposal_findings(
            command.assignment, command.proposal, command.prepared_workspace
        )
    ):
        raise BackendProposalError("Backend proposal contains blocking findings")
    baseline = {item.path: item for item in command.prepared_workspace.baseline.files}
    changes, contents = [], []
    for artifact in command.proposal.artifacts:
        path, content = normalize_managed_path(artifact.path), artifact.content.encode()
        old = baseline.get(path)
        changes.append(
            WorkspaceChange(
                artifact.artifact_id,
                WorkspaceOperation.CREATE_FILE if old is None else WorkspaceOperation.UPDATE_FILE,
                path,
                sha256_bytes(content),
                None if old is None else old.fingerprint,
                artifact.claim_ref,
                artifact.unit_ref,
                "Apply validated backend proposal artifact.",
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


def apply_backend_unit(
    command: ApplyBackendUnitCommand, *, executor: WorkspaceExecutor | None = None
) -> ApplyBackendUnitResult:
    change_set, contents = proposal_to_change_set(command)
    prepared = replace(command.prepared_workspace, change_set=change_set)
    workspace_command = ApplyWorkspaceCommand(
        command.execution_id, command.target, prepared, command.policy, contents
    )
    if dry_run_workspace(workspace_command).policy_violations:
        raise BackendProposalError("Backend change set fails W05 dry-run")
    result = (executor or WorkspaceExecutor()).apply(workspace_command)
    return ApplyBackendUnitResult(command.proposal, result.receipt)


def verify_backend(
    command: VerifyBackendCommand, adapter: BackendStackAdapter
) -> VerifyBackendResult:
    if command.project_status is not WebLifecycleStatus.IMPLEMENTING:
        raise BackendProposalError("Backend verification requires IMPLEMENTING")
    if not adapter.supports(command.prepared_workspace.stack):
        raise UnsupportedBackendStackError("Resolved W05 backend stack is unsupported")
    receipt, proposal = command.applied.receipt, command.applied.proposal
    checks = adapter.verify(proposal, receipt.post_tree_fingerprint)
    findings = list(proposal_findings(command.assignment, proposal, command.prepared_workspace))
    accepted = {FrontendCheckStatus.PASS, FrontendCheckStatus.NOT_APPLICABLE}
    present = {item.kind for item in checks if item.status in accepted}
    for missing in sorted(set(command.required_check_kinds) - present):
        findings.append(
            _finding(
                BackendFindingCode.MISSING_CHECK,
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
                    BackendFindingCode.CHECK_FAILED,
                    f"Engineering check did not pass: {check.kind}",
                    (check.check_id,),
                )
            )
    if receipt.reconciliation_status is ReconciliationStatus.REQUIRED:
        findings.append(
            _finding(
                BackendFindingCode.RECONCILIATION_REQUIRED, "Workspace reconciliation is required"
            )
        )
    unit_results = tuple(
        BackendUnitResult(
            unit,
            bool(
                refs := tuple(
                    item.artifact_id for item in proposal.artifacts if item.unit_ref == unit
                )
            ),
            refs,
        )
        for unit in command.assignment.selected_unit_refs
    )
    blocked = (
        any(item.blocking for item in findings)
        or any(not item.completed for item in unit_results)
        or receipt.outcome
        not in {ExecutionOutcome.APPLIED, ExecutionOutcome.NOOP_ALREADY_SATISFIED}
    )
    frontend = command.frontend_completion
    frontend_ref = ContractRef(
        frontend.contract_type,
        frontend.completion_id,
        frontend.contract_version,
        frontend.canonical_fingerprint(),
    )
    completion = BackendCompletionPackage(
        CURRENT_WEB_CONTRACT_VERSION,
        semantic_id(
            "BCP",
            {
                "assignment": command.assignment,
                "proposal": proposal,
                "receipt": receipt,
                "checks": checks,
                "findings": findings,
            },
        ),
        command.assignment.project_id,
        WebLifecycleStatus.IMPLEMENTING,
        BackendDisposition.BLOCKED if blocked else BackendDisposition.COMPLETE_FOR_REVIEW,
        command.assignment.canonical_fingerprint(),
        proposal.canonical_fingerprint(),
        frontend_ref,
        proposal.bindings,
        unit_results,
        proposal.interface.canonical_fingerprint(),
        proposal.data_contract.canonical_fingerprint(),
        proposal.persistence.canonical_fingerprint(),
        proposal.migrations.canonical_fingerprint(),
        receipt,
        command.assignment.managed_tree_fingerprint,
        receipt.post_tree_fingerprint,
        checks,
        tuple(findings),
        receipt.reconciliation_status,
        tuple(
            sorted(
                {
                    "backend-contracts",
                    "application-data",
                    "authn-authz",
                    "migrations",
                    "integrations",
                }
            )
        ),
    )
    return VerifyBackendResult(completion)


__all__ = (
    "apply_backend_unit",
    "prepare_backend",
    "proposal_findings",
    "proposal_to_change_set",
    "verify_backend",
)
