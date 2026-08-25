"""Deterministic W08 candidate preparation and QA evidence aggregation."""

from __future__ import annotations

from dataclasses import replace

from arch_web.application.architecture.planning import semantic_id
from arch_web.application.qa.errors import QAExecutionError, QAPreparationError
from arch_web.application.qa.models import (
    ExecuteQACommand,
    ExecuteQAResult,
    PrepareQACommand,
    PrepareQAResult,
)
from arch_web.contracts.versions import CURRENT_WEB_CONTRACT_VERSION
from arch_web.domain.backend import BackendDisposition
from arch_web.domain.enums import WebLifecycleStatus, WebRoute
from arch_web.domain.frontend import FrontendReadiness
from arch_web.domain.qa import (
    FunctionalQAEvidence,
    PerformanceQAEvidence,
    PreviewPlan,
    QACandidateBaseline,
    QACoverageDisposition,
    QACoverageItem,
    QACoverageMatrix,
    QAEvidence,
    QAExpectation,
    QAFinding,
    QAFindingDisposition,
    QAReadiness,
    QAReviewPackage,
    QARun,
    QAScenario,
    QAScope,
    QASeverity,
    QAStatus,
    QAStep,
    SecurityBehaviorEvidence,
)
from arch_web.domain.references import ContractRef
from arch_web.domain.workspace import ReconciliationStatus
from arch_web.ports.qa import (
    AccessibilityAuditPort,
    BrowserAutomationPort,
    IntegrationAuditPort,
    PreviewRuntimePort,
    RuntimeObservationPort,
    VisualComparisonPort,
)


def _ref(record: object, record_id: str) -> ContractRef:
    contract_type = str(record.contract_type)  # type: ignore[attr-defined]
    version = str(getattr(record, "contract_version", CURRENT_WEB_CONTRACT_VERSION))
    fingerprint = str(record.canonical_fingerprint())  # type: ignore[attr-defined]
    return ContractRef(contract_type, record_id, version, fingerprint)


def _scenario(command: PrepareQACommand, route_id: str, path: str, surface: str) -> QAScenario:
    components = tuple(
        item for item in command.ui_specification.components if surface in item.surface_refs
    )
    states = tuple(
        f"{item.component_id}:{state.state.value}" for item in components for state in item.states
    )
    operation_refs = (
        ()
        if command.backend_proposal is None
        else tuple(item.operation_id for item in command.backend_proposal.interface.operations)
    )
    responsive_refs = tuple(
        rule.rule_id
        for rule in command.design_system.responsive.rules
        if not rule.target_refs
        or surface in rule.target_refs
        or any(item.component_id in rule.target_refs for item in components)
    )
    security_refs = (
        ()
        if command.backend_proposal is None
        else tuple(item.rule_id for item in command.backend_proposal.authorization_rules)
    )
    viewports = tuple(item.viewport_id for item in command.profile.viewport_policy.viewports)
    expectations = (
        QAExpectation(
            semantic_id("QEX", {"route": route_id, "kind": "landmark"}),
            "dom_contains",
            "body",
            "<main",
            True,
        ),
        QAExpectation(
            semantic_id("QEX", {"route": route_id, "kind": "outcome"}),
            "interaction_text",
            "#feedback",
            "Selected",
            True,
        ),
        QAExpectation(
            semantic_id("QEX", {"route": route_id, "kind": "runtime"}),
            "console_errors",
            "browser",
            "0",
            True,
        ),
    )
    steps = (
        QAStep(
            semantic_id("QST", {"route": route_id, "action": "navigate"}),
            "navigate",
            path,
            None,
            (expectations[0], expectations[2]),
        ),
        QAStep(
            semantic_id("QST", {"route": route_id, "action": "click"}),
            "click",
            "#state-toggle",
            None,
            (expectations[1],),
        ),
    )
    return QAScenario(
        semantic_id("QSC", {"project": command.project_id, "route": route_id}),
        f"Primary governed journey for {route_id}",
        "synthetic-authorized-user",
        command.fixture_id,
        tuple(
            sorted(
                {
                    ref
                    for item in command.prepared_workspace.plan.units
                    if surface in item.surface_refs
                    for ref in item.requirement_refs
                }
                | {
                    ref
                    for item in (
                        ()
                        if command.backend_proposal is None
                        else command.backend_proposal.interface.operations
                    )
                    for ref in item.requirement_refs
                }
            )
        ),
        (route_id,),
        (surface,),
        tuple(item.component_id for item in components),
        states,
        operation_refs,
        responsive_refs,
        security_refs,
        viewports,
        steps,
        command.route is not WebRoute.QUICK,
        1 if command.route is WebRoute.STANDARD else 0,
    )


def prepare_qa(command: PrepareQACommand) -> PrepareQAResult:
    if command.project_status is not WebLifecycleStatus.IMPLEMENTING:
        raise QAPreparationError("QA candidate preparation requires IMPLEMENTING")
    if not command.profile.adopted or command.profile.route is not command.route:
        raise QAPreparationError("QA profile must be explicitly adopted for the project route")
    workspace = command.prepared_workspace
    frontend = command.frontend_completion
    backend = command.backend_completion
    identities = {
        command.project_id,
        workspace.plan.project_id,
        workspace.stack.project_id,
        frontend.project_id,
        backend.project_id,
        command.current_baseline.project_id,
    }
    if len(identities) != 1:
        raise QAPreparationError("QA candidate project identity mismatch")
    if frontend.readiness is not FrontendReadiness.COMPLETE_FOR_REVIEW or frontend.findings:
        raise QAPreparationError("Frontend completion is not ready for independent QA")
    if (
        backend.disposition
        not in {
            BackendDisposition.COMPLETE_FOR_REVIEW,
            BackendDisposition.NOT_APPLICABLE,
        }
        or backend.findings
    ):
        raise QAPreparationError("Backend completion is not valid for QA")
    if frontend.proposal_fingerprint != command.frontend_proposal.canonical_fingerprint():
        raise QAPreparationError("Frontend proposal evidence is stale")
    if backend.disposition is BackendDisposition.NOT_APPLICABLE:
        if command.backend_proposal is not None:
            raise QAPreparationError("Backend N/A candidate cannot include a proposal")
    elif (
        command.backend_proposal is None
        or backend.proposal_fingerprint != command.backend_proposal.canonical_fingerprint()
    ):
        raise QAPreparationError("Backend proposal evidence is stale")
    if backend.frontend_completion_ref.fingerprint != frontend.canonical_fingerprint():
        raise QAPreparationError("W07 completion does not bind exact W06 evidence")
    expected_head = (
        frontend.receipt.repository_evidence.after_head
        if backend.workspace_receipt is None
        else backend.workspace_receipt.repository_evidence.after_head
    )
    exact = (
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
        (workspace.plan.canonical_fingerprint(), frontend.implementation_plan_fingerprint),
        (backend.post_tree_fingerprint, command.current_baseline.tree_fingerprint),
        (expected_head, command.current_baseline.repository.head),
    )
    if any(actual != expected for actual, expected in exact):
        raise QAPreparationError("QA candidate source or upstream evidence is stale")
    if (
        frontend.reconciliation_status is ReconciliationStatus.REQUIRED
        or backend.reconciliation_status is ReconciliationStatus.REQUIRED
    ):
        raise QAPreparationError("QA candidate requires clean reconciliation")
    if command.current_baseline.repository.head is None:
        raise QAPreparationError("QA candidate requires an exact Git HEAD")
    candidate = QACandidateBaseline(
        CURRENT_WEB_CONTRACT_VERSION,
        semantic_id(
            "QCB",
            {
                "project": command.project_id,
                "tree": command.current_baseline.tree_fingerprint,
                "git": command.current_baseline.repository.head,
                "frontend": frontend.canonical_fingerprint(),
                "backend": backend.canonical_fingerprint(),
                "profile": command.profile.canonical_fingerprint(),
            },
        ),
        command.project_id,
        command.route,
        WebLifecycleStatus.IMPLEMENTING,
        command.runtime_record_version,
        command.runtime_record_fingerprint,
        command.requirements_fingerprint,
        command.architecture.canonical_fingerprint(),
        command.design_system.canonical_fingerprint(),
        command.ui_specification.canonical_fingerprint(),
        workspace.plan.canonical_fingerprint(),
        frontend.canonical_fingerprint(),
        backend.canonical_fingerprint(),
        command.current_baseline.tree_fingerprint,
        command.current_baseline.repository.head,
        command.build_artifact_fingerprints,
        command.profile.canonical_fingerprint(),
        ReconciliationStatus.CLEAN,
    )
    scenarios = tuple(
        _scenario(command, item.route_id, item.path_pattern, item.surface_ref)
        for item in command.architecture.routes
    )
    required = {
        *(ref for item in workspace.plan.units for ref in item.requirement_refs),
        *(item.route_id for item in command.architecture.routes),
        *(item.surface_id for item in command.architecture.surfaces),
        *(item.component_id for item in command.ui_specification.components),
        *(
            f"{item.component_id}:{state.state.value}"
            for item in command.ui_specification.components
            for state in item.states
        ),
        *(item.rule_id for item in command.design_system.responsive.rules),
    }
    if command.backend_proposal is not None:
        required |= {
            *(item.operation_id for item in command.backend_proposal.interface.operations),
            *(item.rule_id for item in command.backend_proposal.authorization_rules),
        }
    scope = QAScope(
        CURRENT_WEB_CONTRACT_VERSION,
        semantic_id("QSP", {"candidate": candidate, "scenarios": scenarios}),
        command.project_id,
        command.route,
        candidate.canonical_fingerprint(),
        command.profile.canonical_fingerprint(),
        scenarios,
        tuple(required),
    )
    preview = PreviewPlan(
        semantic_id("PVP", {"candidate": candidate, "entrypoint": command.entrypoint_path}),
        candidate.canonical_fingerprint(),
        command.workspace_root,
        command.entrypoint_path,
        command.fixture_id,
        command.application_database_path,
        command.runtime_database_path,
        10,
    )
    return PrepareQAResult(candidate, scope, preview)


def _evidence[T: QAEvidence](
    cls: type[T],
    category: str,
    candidate: QACandidateBaseline,
    run: QARun,
    refs: tuple[str, ...],
) -> T:
    statuses = {item.status for item in run.results}
    status = (
        QAStatus.FAIL
        if QAStatus.FAIL in statuses
        else QAStatus.FLAKY
        if QAStatus.FLAKY in statuses
        else QAStatus.INCONCLUSIVE
        if QAStatus.INCONCLUSIVE in statuses
        else QAStatus.PASS
    )
    return cls(
        semantic_id("QEV", {"category": category, "candidate": candidate, "run": run}),
        category,
        candidate.canonical_fingerprint(),
        status,
        refs,
        (f"{category} evaluated against exact candidate",),
        tuple(digest for item in run.results for digest in item.evidence_digests),
    )


def execute_qa(
    command: ExecuteQACommand,
    preview_runtime: PreviewRuntimePort,
    browser: BrowserAutomationPort,
    integration_audit: IntegrationAuditPort,
    accessibility: AccessibilityAuditPort,
    visual: VisualComparisonPort,
    observation: RuntimeObservationPort,
) -> ExecuteQAResult:
    prepared, candidate = command.prepared, command.prepared.candidate
    if command.project_status is not WebLifecycleStatus.TESTING:
        raise QAExecutionError("QA execution requires TESTING")
    if (
        not command.authorization.authorized
        or command.authorization.runtime_state is not WebLifecycleStatus.TESTING
    ):
        raise QAExecutionError("QA execution lacks Runtime authorization")
    if command.authorization.candidate_fingerprint != candidate.canonical_fingerprint():
        raise QAExecutionError("QA execution authorization is stale")
    if command.profile.canonical_fingerprint() != candidate.qa_profile_fingerprint:
        raise QAExecutionError("QA profile differs from frozen candidate")
    session = preview_runtime.start(prepared.preview_plan)
    started = session.evidence
    if not started.ready:
        session.stop()
        raise QAExecutionError("Local preview did not become ready")
    results = []
    try:
        for scenario in prepared.scope.scenarios:
            for viewport_ref in scenario.viewport_refs:
                viewport = next(
                    item
                    for item in command.profile.viewport_policy.viewports
                    if item.viewport_id == viewport_ref
                )
                attempts = []
                result = browser.execute(scenario, candidate, started.endpoint, viewport)
                attempts.append(result.status)
                for _ in range(scenario.retry_limit):
                    if result.status is QAStatus.PASS:
                        break
                    result = browser.execute(scenario, candidate, started.endpoint, viewport)
                    attempts.append(result.status)
                    if result.status is QAStatus.PASS:
                        break
                expected_binding = (
                    result.scenario_ref == scenario.scenario_id
                    and result.candidate_fingerprint == candidate.canonical_fingerprint()
                    and result.source_tree_fingerprint == candidate.source_tree_fingerprint
                    and result.git_head == candidate.git_head
                    and result.viewport_ref == viewport.viewport_id
                )
                if not expected_binding:
                    raise QAExecutionError("Browser result does not bind the exact QA candidate")
                if len(set(attempts)) > 1:
                    result = replace(
                        result,
                        status=QAStatus.FLAKY,
                        attempt_statuses=tuple(attempts),
                    )
                elif len(attempts) > 1:
                    result = replace(result, attempt_statuses=tuple(attempts))
                results.append(result)
    finally:
        preview = session.stop()
    run = QARun(
        CURRENT_WEB_CONTRACT_VERSION,
        semantic_id("QRN", {"candidate": candidate, "results": results, "environment": preview}),
        candidate.canonical_fingerprint(),
        prepared.scope.canonical_fingerprint(),
        preview.canonical_fingerprint(),
        tuple(results),
        command.started_at,
        command.finished_at,
    )
    scenario_refs = tuple(sorted({item.scenario_ref for item in run.results}))
    functional = _evidence(FunctionalQAEvidence, "functional", candidate, run, scenario_refs)
    integration = integration_audit.audit(candidate, run)
    security = _evidence(SecurityBehaviorEvidence, "security", candidate, run, scenario_refs)
    if integration.status is not QAStatus.PASS:
        security = replace(
            security,
            status=integration.status,
            observations=(*security.observations, "backend security evidence did not pass"),
        )
    performance = _evidence(
        PerformanceQAEvidence,
        "performance-advisory",
        candidate,
        run,
        scenario_refs,
    )
    access = accessibility.audit(candidate, run)
    responsive = observation.responsive_evidence(candidate, run)
    visual_evidence = visual.compare(candidate, run)
    all_evidence = (
        functional,
        integration,
        access,
        responsive,
        visual_evidence,
        performance,
        security,
    )
    findings: list[QAFinding] = []
    scenario_by_id = {item.scenario_id: item for item in prepared.scope.scenarios}
    for result in run.results:
        scenario = scenario_by_id[result.scenario_ref]
        if result.status in {QAStatus.FAIL, QAStatus.FLAKY, QAStatus.INCONCLUSIVE}:
            severity = QASeverity.BLOCKER if scenario.critical else QASeverity.MAJOR
            findings.append(
                QAFinding(
                    semantic_id("QFD", {"result": result, "candidate": candidate}),
                    candidate.canonical_fingerprint(),
                    f"qa_{result.status.value}",
                    severity,
                    QAFindingDisposition.OPEN,
                    scenario.scenario_id,
                    f"Scenario did not produce stable passing evidence: {result.status.value}",
                    result.evidence_digests,
                    scenario.requirement_refs,
                )
            )
    for evidence in all_evidence:
        if evidence.status in {QAStatus.FAIL, QAStatus.FLAKY, QAStatus.INCONCLUSIVE}:
            findings.append(
                QAFinding(
                    semantic_id("QFD", {"evidence": evidence}),
                    candidate.canonical_fingerprint(),
                    f"{evidence.category}_not_passed",
                    QASeverity.MAJOR,
                    QAFindingDisposition.OPEN,
                    None,
                    f"Required {evidence.category} evidence did not pass",
                    (evidence.evidence_id,),
                    evidence.covered_refs,
                )
            )
    evidence_ids = tuple(item.evidence_id for item in all_evidence)
    coverage_items = []
    for ref in prepared.scope.required_coverage_refs:
        scenarios = tuple(
            scenario.scenario_id
            for scenario in prepared.scope.scenarios
            if ref
            in {
                *scenario.requirement_refs,
                *scenario.route_refs,
                *scenario.surface_refs,
                *scenario.component_refs,
                *scenario.component_state_refs,
                *scenario.backend_operation_refs,
                *scenario.responsive_rule_refs,
                *scenario.security_rule_refs,
            }
        )
        covered = bool(scenarios) and any(
            result.scenario_ref in scenarios and result.status is QAStatus.PASS
            for result in run.results
        )
        coverage_items.append(
            QACoverageItem(
                ref,
                QACoverageDisposition.TESTED if covered else QACoverageDisposition.NOT_TESTED,
                scenarios,
                evidence_ids if covered else (),
                "Exact candidate execution evidence" if covered else "No passing scenario evidence",
                True,
            )
        )
    matrix = QACoverageMatrix(
        semantic_id("QCM", {"candidate": candidate, "items": coverage_items}),
        candidate.canonical_fingerprint(),
        tuple(coverage_items),
    )
    if any(
        item.material and item.disposition is QACoverageDisposition.NOT_TESTED
        for item in matrix.items
    ):
        findings.append(
            QAFinding(
                semantic_id("QFD", {"candidate": candidate, "code": "missing_coverage"}),
                candidate.canonical_fingerprint(),
                "missing_material_coverage",
                QASeverity.MAJOR,
                QAFindingDisposition.OPEN,
                None,
                "Material QA coverage is missing",
                (),
                tuple(
                    item.coverage_ref
                    for item in matrix.items
                    if item.disposition is QACoverageDisposition.NOT_TESTED
                ),
            )
        )
    if not preview.cleanup_verified:
        findings.append(
            QAFinding(
                semantic_id("QFD", {"candidate": candidate, "code": "cleanup"}),
                candidate.canonical_fingerprint(),
                "preview_cleanup_failed",
                QASeverity.BLOCKER,
                QAFindingDisposition.OPEN,
                None,
                "Preview cleanup was not verified",
                (preview.environment_id,),
                (),
            )
        )
    findings_tuple = tuple(
        sorted(
            {item.finding_id: item for item in findings}.values(),
            key=lambda item: item.finding_id,
        )
    )
    refs = tuple(_ref(item, item.evidence_id) for item in all_evidence)
    blocked = any(item.blocking for item in findings_tuple)
    review = QAReviewPackage(
        CURRENT_WEB_CONTRACT_VERSION,
        semantic_id("QRV", {"candidate": candidate, "run": run, "findings": findings_tuple}),
        candidate.project_id,
        _ref(candidate, candidate.candidate_id),
        _ref(prepared.scope, prepared.scope.scope_id),
        _ref(run, run.run_id),
        _ref(preview, preview.environment_id),
        refs,
        matrix,
        findings_tuple,
        ReconciliationStatus.CLEAN,
        QAReadiness.BLOCKED if blocked else QAReadiness.READY_FOR_REVIEW,
    )
    return ExecuteQAResult(
        preview,
        run,
        functional,
        integration,
        access,
        responsive,
        visual_evidence,
        performance,
        security,
        matrix,
        findings_tuple,
        review,
    )


__all__ = ("execute_qa", "prepare_qa")
