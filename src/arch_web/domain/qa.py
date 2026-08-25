"""Immutable W08 testing, preview, and design-QA contracts."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum, unique

from arch_web.contracts.versions import require_supported_version
from arch_web.domain._base import WebContractRecord, freeze_strings, require_text
from arch_web.domain.enums import WebLifecycleStatus, WebRoute
from arch_web.domain.references import ContractRef, EvidenceRef
from arch_web.domain.workspace import ReconciliationStatus


def _records[T](values: tuple[T, ...], key: Callable[[T], str], label: str) -> tuple[T, ...]:
    ordered = tuple(sorted(values, key=key))
    keys = tuple(key(item) for item in ordered)
    if len(keys) != len(set(keys)):
        raise ValueError(f"{label} must be unique")
    return ordered


@unique
class QAStatus(StrEnum):
    PASS = "pass"
    FAIL = "fail"
    FLAKY = "flaky"
    INCONCLUSIVE = "inconclusive"
    NOT_APPLICABLE = "not_applicable"


@unique
class QASeverity(StrEnum):
    BLOCKER = "blocker"
    CRITICAL = "critical"
    MAJOR = "major"
    MINOR = "minor"
    ADVISORY = "advisory"


@unique
class QAFindingDisposition(StrEnum):
    OPEN = "open"
    FIXED_PENDING_RERUN = "fixed_pending_rerun"
    VERIFIED_FIXED = "verified_fixed"
    NOT_APPLICABLE = "not_applicable"
    ACCEPTED_RISK = "accepted_risk"
    FALSE_POSITIVE = "false_positive"


@unique
class QACoverageDisposition(StrEnum):
    TESTED = "tested"
    NOT_TESTED = "not_tested"
    NOT_APPLICABLE = "not_applicable"


@unique
class QAReadiness(StrEnum):
    BLOCKED = "blocked"
    READY_FOR_REVIEW = "ready_for_review"
    APPROVED = "approved"


@unique
class VisualComparisonDisposition(StrEnum):
    STRUCTURAL_ONLY = "structural_only"
    BASELINE_MATCH = "baseline_match"
    BASELINE_MISMATCH = "baseline_mismatch"
    STALE_BASELINE = "stale_baseline"


@dataclass(frozen=True, slots=True)
class BrowserSupportPolicy(WebContractRecord):
    contract_type = "browser_support_policy"
    policy_id: str
    engines: tuple[str, ...]
    browser_versions: tuple[str, ...]
    console_errors_block: bool
    external_network_allowed: bool = False

    def __post_init__(self) -> None:
        require_text(self.policy_id, "policy_id")
        if not self.engines or len(self.engines) != len(self.browser_versions):
            raise ValueError("Browser policy requires explicit engine/version pairs")
        pairs = tuple(
            sorted(
                (
                    require_text(engine, "engines"),
                    require_text(version, "browser_versions"),
                )
                for engine, version in zip(self.engines, self.browser_versions, strict=True)
            )
        )
        if len({engine for engine, _ in pairs}) != len(pairs):
            raise ValueError("Browser engines must be unique")
        object.__setattr__(self, "engines", tuple(engine for engine, _ in pairs))
        object.__setattr__(self, "browser_versions", tuple(version for _, version in pairs))


@dataclass(frozen=True, slots=True)
class ViewportSpec(WebContractRecord):
    contract_type = "viewport_spec"
    viewport_id: str
    width: int
    height: int
    touch: bool

    def __post_init__(self) -> None:
        require_text(self.viewport_id, "viewport_id")
        if self.width < 240 or self.height < 240:
            raise ValueError("Viewport dimensions are implausibly small")


@dataclass(frozen=True, slots=True)
class ViewportPolicy(WebContractRecord):
    contract_type = "viewport_policy"
    policy_id: str
    viewports: tuple[ViewportSpec, ...]
    breakpoint_boundaries: tuple[int, ...]

    def __post_init__(self) -> None:
        require_text(self.policy_id, "policy_id")
        object.__setattr__(
            self, "viewports", _records(self.viewports, lambda item: item.viewport_id, "viewports")
        )
        boundaries = tuple(sorted(set(self.breakpoint_boundaries)))
        if any(value < 240 for value in boundaries):
            raise ValueError("Breakpoint boundary is implausibly small")
        object.__setattr__(self, "breakpoint_boundaries", boundaries)


@dataclass(frozen=True, slots=True)
class QABaselineProfile(WebContractRecord):
    contract_type = "qa_baseline_profile"
    contract_version: str
    profile_id: str
    route: WebRoute
    browser_policy: BrowserSupportPolicy
    viewport_policy: ViewportPolicy
    accessibility_policy: tuple[str, ...]
    runtime_observation_policy: tuple[str, ...]
    visual_threshold: float | None
    visual_baseline_ref: EvidenceRef | None
    performance_budgets: tuple[tuple[str, float], ...]
    adopted: bool

    def __post_init__(self) -> None:
        require_supported_version(self.contract_version)
        require_text(self.profile_id, "profile_id")
        for name in ("accessibility_policy", "runtime_observation_policy"):
            object.__setattr__(self, name, freeze_strings(getattr(self, name), name, sort=True))
        budgets = tuple(sorted(self.performance_budgets))
        if len({name for name, _ in budgets}) != len(budgets):
            raise ValueError("Performance budget names must be unique")
        if any(value <= 0 for _, value in budgets):
            raise ValueError("Performance budgets must be positive")
        object.__setattr__(self, "performance_budgets", budgets)
        if self.visual_threshold is not None and not 0 <= self.visual_threshold <= 1:
            raise ValueError("Visual threshold must be between zero and one")
        if self.visual_baseline_ref is None and self.visual_threshold is not None:
            raise ValueError("A visual threshold requires an approved baseline")


@dataclass(frozen=True, slots=True)
class QACandidateBaseline(WebContractRecord):
    contract_type = "qa_candidate_baseline"
    contract_version: str
    candidate_id: str
    project_id: str
    route: WebRoute
    runtime_state: WebLifecycleStatus
    runtime_record_version: int
    runtime_record_fingerprint: str
    requirements_fingerprint: str
    architecture_fingerprint: str
    design_system_fingerprint: str
    ui_specification_fingerprint: str
    implementation_plan_fingerprint: str
    frontend_completion_fingerprint: str
    backend_completion_fingerprint: str
    source_tree_fingerprint: str
    git_head: str
    build_artifact_fingerprints: tuple[str, ...]
    qa_profile_fingerprint: str
    reconciliation_status: ReconciliationStatus

    def __post_init__(self) -> None:
        require_supported_version(self.contract_version)
        for name in (
            "candidate_id",
            "project_id",
            "runtime_record_fingerprint",
            "requirements_fingerprint",
            "architecture_fingerprint",
            "design_system_fingerprint",
            "ui_specification_fingerprint",
            "implementation_plan_fingerprint",
            "frontend_completion_fingerprint",
            "backend_completion_fingerprint",
            "source_tree_fingerprint",
            "git_head",
            "qa_profile_fingerprint",
        ):
            require_text(getattr(self, name), name)
        if self.runtime_state is not WebLifecycleStatus.IMPLEMENTING:
            raise ValueError("QA candidate freeze requires IMPLEMENTING")
        if self.runtime_record_version < 1:
            raise ValueError("runtime_record_version must be positive")
        object.__setattr__(
            self,
            "build_artifact_fingerprints",
            freeze_strings(
                self.build_artifact_fingerprints, "build_artifact_fingerprints", sort=True
            ),
        )
        if self.reconciliation_status is not ReconciliationStatus.CLEAN:
            raise ValueError("QA candidate requires clean reconciliation")


@dataclass(frozen=True, slots=True)
class QAExpectation(WebContractRecord):
    contract_type = "qa_expectation"
    expectation_id: str
    kind: str
    target: str
    expected_value: str
    blocking: bool

    def __post_init__(self) -> None:
        for name in ("expectation_id", "kind", "target", "expected_value"):
            require_text(getattr(self, name), name)


@dataclass(frozen=True, slots=True)
class QAStep(WebContractRecord):
    contract_type = "qa_step"
    step_id: str
    action: str
    target: str
    value: str | None
    expectations: tuple[QAExpectation, ...]

    def __post_init__(self) -> None:
        for name in ("step_id", "action", "target"):
            require_text(getattr(self, name), name)
        if self.value is not None:
            require_text(self.value, "value")
        object.__setattr__(
            self,
            "expectations",
            _records(self.expectations, lambda item: item.expectation_id, "expectations"),
        )
        if not self.expectations:
            raise ValueError("QA step requires an observable expectation")


@dataclass(frozen=True, slots=True)
class QAScenario(WebContractRecord):
    contract_type = "qa_scenario"
    scenario_id: str
    title: str
    actor: str
    fixture_ref: str
    requirement_refs: tuple[str, ...]
    route_refs: tuple[str, ...]
    surface_refs: tuple[str, ...]
    component_refs: tuple[str, ...]
    component_state_refs: tuple[str, ...]
    backend_operation_refs: tuple[str, ...]
    responsive_rule_refs: tuple[str, ...]
    security_rule_refs: tuple[str, ...]
    viewport_refs: tuple[str, ...]
    steps: tuple[QAStep, ...]
    critical: bool
    retry_limit: int = 0

    def __post_init__(self) -> None:
        for name in ("scenario_id", "title", "actor", "fixture_ref"):
            require_text(getattr(self, name), name)
        for name in (
            "requirement_refs",
            "route_refs",
            "surface_refs",
            "component_refs",
            "component_state_refs",
            "backend_operation_refs",
            "responsive_rule_refs",
            "security_rule_refs",
            "viewport_refs",
        ):
            object.__setattr__(self, name, freeze_strings(getattr(self, name), name, sort=True))
        object.__setattr__(self, "steps", tuple(self.steps))
        if not self.steps:
            raise ValueError("QA scenario requires steps")
        if self.retry_limit < 0 or self.retry_limit > 2:
            raise ValueError("QA retry limit must be bounded")


@dataclass(frozen=True, slots=True)
class QAScope(WebContractRecord):
    contract_type = "qa_scope"
    contract_version: str
    scope_id: str
    project_id: str
    route: WebRoute
    candidate_fingerprint: str
    profile_fingerprint: str
    scenarios: tuple[QAScenario, ...]
    required_coverage_refs: tuple[str, ...]

    def __post_init__(self) -> None:
        require_supported_version(self.contract_version)
        for name in ("scope_id", "project_id", "candidate_fingerprint", "profile_fingerprint"):
            require_text(getattr(self, name), name)
        object.__setattr__(
            self, "scenarios", _records(self.scenarios, lambda item: item.scenario_id, "scenarios")
        )
        object.__setattr__(
            self,
            "required_coverage_refs",
            freeze_strings(self.required_coverage_refs, "required_coverage_refs", sort=True),
        )
        if not self.scenarios:
            raise ValueError("QA scope requires scenarios")


@dataclass(frozen=True, slots=True)
class QAExecutionAuthorization(WebContractRecord):
    contract_type = "qa_execution_authorization"
    contract_version: str
    authorization_id: str
    project_id: str
    candidate_fingerprint: str
    scope_fingerprint: str
    profile_fingerprint: str
    runtime_state: WebLifecycleStatus
    authorized: bool

    def __post_init__(self) -> None:
        require_supported_version(self.contract_version)
        for name in (
            "authorization_id",
            "project_id",
            "candidate_fingerprint",
            "scope_fingerprint",
            "profile_fingerprint",
        ):
            require_text(getattr(self, name), name)
        if self.authorized and self.runtime_state is not WebLifecycleStatus.TESTING:
            raise ValueError("Authorized QA execution requires TESTING")


@dataclass(frozen=True, slots=True)
class PreviewPlan(WebContractRecord):
    contract_type = "preview_plan"
    plan_id: str
    candidate_fingerprint: str
    workspace_root: str
    entrypoint_path: str
    fixture_id: str
    application_database_path: str | None
    runtime_database_path: str | None
    readiness_timeout_seconds: int

    def __post_init__(self) -> None:
        for name in (
            "plan_id",
            "candidate_fingerprint",
            "workspace_root",
            "entrypoint_path",
            "fixture_id",
        ):
            require_text(getattr(self, name), name)
        if self.readiness_timeout_seconds < 1 or self.readiness_timeout_seconds > 60:
            raise ValueError("Preview readiness timeout is out of bounds")
        if (
            self.application_database_path is not None
            and self.runtime_database_path is not None
            and self.application_database_path.casefold() == self.runtime_database_path.casefold()
        ):
            raise ValueError("Preview application database must be separate from Runtime")


@dataclass(frozen=True, slots=True)
class PreviewEnvironmentEvidence(WebContractRecord):
    contract_type = "preview_environment_evidence"
    environment_id: str
    candidate_fingerprint: str
    endpoint: str
    adapter_identity: str
    process_id: int
    fixture_fingerprint: str
    ready: bool
    sanitized_log_digest: str
    cleanup_verified: bool

    def __post_init__(self) -> None:
        for name in (
            "environment_id",
            "candidate_fingerprint",
            "endpoint",
            "adapter_identity",
            "fixture_fingerprint",
            "sanitized_log_digest",
        ):
            require_text(getattr(self, name), name)
        if self.process_id < 1:
            raise ValueError("Preview process ID must be positive")


@dataclass(frozen=True, slots=True)
class QAResult(WebContractRecord):
    contract_type = "qa_result"
    result_id: str
    scenario_ref: str
    candidate_fingerprint: str
    source_tree_fingerprint: str
    git_head: str
    browser_identity: str
    viewport_ref: str
    status: QAStatus
    attempt_statuses: tuple[QAStatus, ...]
    assertion_count: int
    evidence_digests: tuple[str, ...]
    sanitized_diagnostics: tuple[str, ...]

    def __post_init__(self) -> None:
        for name in (
            "result_id",
            "scenario_ref",
            "candidate_fingerprint",
            "source_tree_fingerprint",
            "git_head",
            "browser_identity",
            "viewport_ref",
        ):
            require_text(getattr(self, name), name)
        object.__setattr__(self, "attempt_statuses", tuple(self.attempt_statuses))
        object.__setattr__(
            self,
            "evidence_digests",
            freeze_strings(self.evidence_digests, "evidence_digests", sort=True),
        )
        object.__setattr__(
            self,
            "sanitized_diagnostics",
            freeze_strings(self.sanitized_diagnostics, "sanitized_diagnostics", sort=True),
        )
        if not self.attempt_statuses or len(self.attempt_statuses) > 3:
            raise ValueError("QA attempts must be present and bounded")
        observed = set(self.attempt_statuses)
        if len(observed) > 1 and self.status is not QAStatus.FLAKY:
            raise ValueError("Inconsistent attempts must remain FLAKY")
        if self.status is QAStatus.PASS and self.assertion_count < 1:
            raise ValueError("Passing QA result requires assertions")


@dataclass(frozen=True, slots=True)
class QARun(WebContractRecord):
    contract_type = "qa_run"
    contract_version: str
    run_id: str
    candidate_fingerprint: str
    scope_fingerprint: str
    environment_fingerprint: str
    results: tuple[QAResult, ...]
    started_at: str
    finished_at: str

    def __post_init__(self) -> None:
        require_supported_version(self.contract_version)
        for name in (
            "run_id",
            "candidate_fingerprint",
            "scope_fingerprint",
            "environment_fingerprint",
            "started_at",
            "finished_at",
        ):
            require_text(getattr(self, name), name)
        object.__setattr__(
            self, "results", _records(self.results, lambda item: item.result_id, "QA results")
        )


@dataclass(frozen=True, slots=True)
class QAEvidence(WebContractRecord):
    contract_type = "qa_evidence"
    evidence_id: str
    category: str
    candidate_fingerprint: str
    status: QAStatus
    covered_refs: tuple[str, ...]
    observations: tuple[str, ...]
    artifact_digests: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for name in ("evidence_id", "category", "candidate_fingerprint"):
            require_text(getattr(self, name), name)
        for name in ("covered_refs", "observations", "artifact_digests"):
            object.__setattr__(self, name, freeze_strings(getattr(self, name), name, sort=True))


@dataclass(frozen=True, slots=True)
class FunctionalQAEvidence(QAEvidence):
    contract_type = "functional_qa_evidence"


@dataclass(frozen=True, slots=True)
class IntegrationQAEvidence(QAEvidence):
    contract_type = "integration_qa_evidence"


@dataclass(frozen=True, slots=True)
class AccessibilityQAEvidence(QAEvidence):
    contract_type = "accessibility_qa_evidence"


@dataclass(frozen=True, slots=True)
class ResponsiveQAEvidence(QAEvidence):
    contract_type = "responsive_qa_evidence"


@dataclass(frozen=True, slots=True)
class PerformanceQAEvidence(QAEvidence):
    contract_type = "performance_qa_evidence"


@dataclass(frozen=True, slots=True)
class SecurityBehaviorEvidence(QAEvidence):
    contract_type = "security_behavior_evidence"


@dataclass(frozen=True, slots=True)
class VisualQAEvidence(QAEvidence):
    contract_type = "visual_qa_evidence"
    comparison: VisualComparisonDisposition = VisualComparisonDisposition.STRUCTURAL_ONLY
    baseline_fingerprint: str | None = None
    threshold: float | None = None

    def __post_init__(self) -> None:
        QAEvidence.__post_init__(self)
        if self.baseline_fingerprint is not None:
            require_text(self.baseline_fingerprint, "baseline_fingerprint")
        if self.comparison is VisualComparisonDisposition.STRUCTURAL_ONLY:
            if self.baseline_fingerprint is not None or self.threshold is not None:
                raise ValueError("Structural-only QA cannot claim pixel baseline comparison")
        elif self.baseline_fingerprint is None or self.threshold is None:
            raise ValueError("Visual comparison requires baseline and threshold")


@dataclass(frozen=True, slots=True)
class QAFinding(WebContractRecord):
    contract_type = "qa_finding"
    finding_id: str
    candidate_fingerprint: str
    code: str
    severity: QASeverity
    disposition: QAFindingDisposition
    scenario_ref: str | None
    message: str
    evidence_refs: tuple[str, ...]
    contract_refs: tuple[str, ...]
    authority_ref: str | None = None

    def __post_init__(self) -> None:
        for name in ("finding_id", "candidate_fingerprint", "code", "message"):
            require_text(getattr(self, name), name)
        if self.scenario_ref is not None:
            require_text(self.scenario_ref, "scenario_ref")
        for name in ("evidence_refs", "contract_refs"):
            object.__setattr__(self, name, freeze_strings(getattr(self, name), name, sort=True))
        if self.authority_ref is not None:
            require_text(self.authority_ref, "authority_ref")
        if (
            self.disposition
            in {
                QAFindingDisposition.ACCEPTED_RISK,
                QAFindingDisposition.FALSE_POSITIVE,
            }
            and self.authority_ref is None
        ):
            raise ValueError("Finding disposition requires external reviewer authority")

    @property
    def blocking(self) -> bool:
        return self.severity in {
            QASeverity.BLOCKER,
            QASeverity.CRITICAL,
            QASeverity.MAJOR,
        } and self.disposition not in {
            QAFindingDisposition.VERIFIED_FIXED,
            QAFindingDisposition.NOT_APPLICABLE,
            QAFindingDisposition.ACCEPTED_RISK,
            QAFindingDisposition.FALSE_POSITIVE,
        }


@dataclass(frozen=True, slots=True)
class QACoverageItem(WebContractRecord):
    contract_type = "qa_coverage_item"
    coverage_ref: str
    disposition: QACoverageDisposition
    scenario_refs: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    rationale: str
    material: bool

    def __post_init__(self) -> None:
        require_text(self.coverage_ref, "coverage_ref")
        require_text(self.rationale, "rationale")
        for name in ("scenario_refs", "evidence_refs"):
            object.__setattr__(self, name, freeze_strings(getattr(self, name), name, sort=True))
        if self.disposition is QACoverageDisposition.TESTED and (
            not self.scenario_refs or not self.evidence_refs
        ):
            raise ValueError("Tested coverage requires scenario and evidence")


@dataclass(frozen=True, slots=True)
class QACoverageMatrix(WebContractRecord):
    contract_type = "qa_coverage_matrix"
    matrix_id: str
    candidate_fingerprint: str
    items: tuple[QACoverageItem, ...]

    def __post_init__(self) -> None:
        require_text(self.matrix_id, "matrix_id")
        require_text(self.candidate_fingerprint, "candidate_fingerprint")
        object.__setattr__(
            self, "items", _records(self.items, lambda item: item.coverage_ref, "coverage items")
        )


@dataclass(frozen=True, slots=True)
class QAReviewPackage(WebContractRecord):
    contract_type = "qa_review_package"
    contract_version: str
    review_id: str
    project_id: str
    candidate_ref: ContractRef
    scope_ref: ContractRef
    run_ref: ContractRef
    preview_ref: ContractRef
    evidence_refs: tuple[ContractRef, ...]
    coverage_matrix: QACoverageMatrix
    findings: tuple[QAFinding, ...]
    reconciliation_status: ReconciliationStatus
    readiness: QAReadiness
    approval_evidence: EvidenceRef | None = None

    def __post_init__(self) -> None:
        require_supported_version(self.contract_version)
        require_text(self.review_id, "review_id")
        require_text(self.project_id, "project_id")
        object.__setattr__(
            self,
            "evidence_refs",
            tuple(sorted(self.evidence_refs, key=lambda item: item.contract_id)),
        )
        object.__setattr__(
            self, "findings", _records(self.findings, lambda item: item.finding_id, "QA findings")
        )
        blocked = (
            any(item.blocking for item in self.findings)
            or any(
                item.material and item.disposition is QACoverageDisposition.NOT_TESTED
                for item in self.coverage_matrix.items
            )
            or self.reconciliation_status is ReconciliationStatus.REQUIRED
        )
        if blocked != (self.readiness is QAReadiness.BLOCKED):
            raise ValueError("QA readiness contradicts evidence")
        if self.readiness is QAReadiness.APPROVED and self.approval_evidence is None:
            raise ValueError("Approved QA review requires explicit approval evidence")


@dataclass(frozen=True, slots=True)
class ReleaseReadinessPackage(WebContractRecord):
    contract_type = "release_readiness_package"
    contract_version: str
    package_id: str
    project_id: str
    runtime_state: WebLifecycleStatus
    candidate_fingerprint: str
    source_tree_fingerprint: str
    git_head: str
    profile_fingerprint: str
    scope_fingerprint: str
    preview_fingerprint: str
    run_fingerprint: str
    coverage_fingerprint: str
    evidence_fingerprints: tuple[str, ...]
    findings: tuple[QAFinding, ...]
    reconciliation_status: ReconciliationStatus
    approval_evidence: EvidenceRef

    def __post_init__(self) -> None:
        require_supported_version(self.contract_version)
        for name in (
            "package_id",
            "project_id",
            "candidate_fingerprint",
            "source_tree_fingerprint",
            "git_head",
            "profile_fingerprint",
            "scope_fingerprint",
            "preview_fingerprint",
            "run_fingerprint",
            "coverage_fingerprint",
        ):
            require_text(getattr(self, name), name)
        if self.runtime_state is not WebLifecycleStatus.TESTING:
            raise ValueError("Release-readiness package requires TESTING")
        object.__setattr__(
            self,
            "evidence_fingerprints",
            freeze_strings(self.evidence_fingerprints, "evidence_fingerprints", sort=True),
        )
        object.__setattr__(
            self, "findings", _records(self.findings, lambda item: item.finding_id, "QA findings")
        )
        if any(item.blocking for item in self.findings):
            raise ValueError("Blocking QA findings prevent release readiness")
        if self.reconciliation_status is not ReconciliationStatus.CLEAN:
            raise ValueError("Release readiness requires clean reconciliation")


__all__ = tuple(
    name
    for name in globals()
    if name.startswith(
        (
            "Accessibility",
            "Browser",
            "Functional",
            "Integration",
            "Performance",
            "Preview",
            "QA",
            "Release",
            "Responsive",
            "Security",
            "Viewport",
            "Visual",
        )
    )
)
