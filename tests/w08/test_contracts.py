"""W08 immutable contract, codec, and invariant tests."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import FrozenInstanceError, replace
from pathlib import Path

import pytest

from arch_web import (
    BrowserSupportPolicy,
    EvidenceRef,
    QACoverageDisposition,
    QACoverageItem,
    QAFinding,
    QAFindingDisposition,
    QAReadiness,
    QAResult,
    QASeverity,
    QAStatus,
    ReconciliationStatus,
    ReleaseReadinessPackage,
    ViewportSpec,
    VisualComparisonDisposition,
    WebLifecycleStatus,
    decode_contract,
    encode_contract,
)
from arch_web.contracts.versions import CURRENT_WEB_CONTRACT_VERSION
from arch_web.domain._base import WebContractRecord
from w08.factories import qa_bundle
from w08.fakes import SequencedBrowser
from w08.test_aggregation import _execute


def test_core_contracts_are_frozen_and_canonically_decodable(tmp_path: Path) -> None:
    _, prepared, profile = qa_bundle(tmp_path)
    executed = _execute(prepared, profile, SequencedBrowser((QAStatus.PASS,)))
    records: tuple[WebContractRecord, ...] = (
        profile.browser_policy,
        *profile.viewport_policy.viewports,
        profile.viewport_policy,
        profile,
        prepared.candidate,
        *prepared.scope.scenarios[0].steps[0].expectations,
        *prepared.scope.scenarios[0].steps,
        *prepared.scope.scenarios,
        prepared.scope,
        prepared.preview_plan,
        executed.preview,
        *executed.run.results,
        executed.run,
        executed.functional,
        executed.integration,
        executed.accessibility,
        executed.responsive,
        executed.visual,
        executed.performance,
        executed.security,
        *executed.coverage.items,
        executed.coverage,
        executed.review,
    )
    for record in records:
        assert decode_contract(type(record), encode_contract(record)) == record
        assert (
            record.canonical_fingerprint()
            == decode_contract(type(record), encode_contract(record)).canonical_fingerprint()
        )
    with pytest.raises(FrozenInstanceError):
        prepared.candidate.git_head = "changed"


@pytest.mark.parametrize(
    "factory",
    [
        lambda: BrowserSupportPolicy("browser", (), (), True),
        lambda: BrowserSupportPolicy("browser", ("chromium",), (), True),
        lambda: ViewportSpec("tiny", 100, 800, False),
    ],
)
def test_profile_primitives_fail_closed(factory: Callable[[], object]) -> None:
    with pytest.raises(ValueError, match=r"."):
        factory()


def test_candidate_scope_scenario_and_preview_invariants(tmp_path: Path) -> None:
    _, prepared, profile = qa_bundle(tmp_path)
    candidate, scope, scenario, plan = (
        prepared.candidate,
        prepared.scope,
        prepared.scope.scenarios[0],
        prepared.preview_plan,
    )
    invalid: tuple[Callable[[], object], ...] = (
        lambda: replace(candidate, runtime_state=WebLifecycleStatus.TESTING),
        lambda: replace(candidate, runtime_record_version=0),
        lambda: replace(candidate, reconciliation_status=ReconciliationStatus.REQUIRED),
        lambda: replace(scope, scenarios=()),
        lambda: replace(scenario, steps=()),
        lambda: replace(scenario, retry_limit=3),
        lambda: replace(plan, readiness_timeout_seconds=0),
        lambda: replace(plan, runtime_database_path=plan.application_database_path),
        lambda: replace(profile, visual_threshold=0.1),
        lambda: replace(profile, performance_budgets=(("budget", 0.0),)),
    )
    for operation in invalid:
        with pytest.raises(ValueError, match=r"."):
            operation()


def test_result_flaky_and_coverage_invariants(tmp_path: Path) -> None:
    _, prepared, _ = qa_bundle(tmp_path)
    scenario = prepared.scope.scenarios[0]
    base = QAResult(
        "QRS-contract",
        scenario.scenario_id,
        prepared.candidate.canonical_fingerprint(),
        prepared.candidate.source_tree_fingerprint,
        prepared.candidate.git_head,
        "chromium/1",
        scenario.viewport_refs[0],
        QAStatus.PASS,
        (QAStatus.PASS,),
        1,
        ("sha256:evidence",),
        (),
    )
    operations: tuple[Callable[[], object], ...] = (
        lambda: replace(base, attempt_statuses=()),
        lambda: replace(base, assertion_count=0),
        lambda: replace(
            base,
            status=QAStatus.PASS,
            attempt_statuses=(QAStatus.FAIL, QAStatus.PASS),
        ),
        lambda: QACoverageItem(
            "REQ-core", QACoverageDisposition.TESTED, (), (), "missing evidence", True
        ),
    )
    for operation in operations:
        with pytest.raises(ValueError, match=r"."):
            operation()
    flaky = replace(
        base,
        status=QAStatus.FLAKY,
        attempt_statuses=(QAStatus.FAIL, QAStatus.PASS),
    )
    assert flaky.status is QAStatus.FLAKY


def test_finding_authority_and_release_readiness_invariants(tmp_path: Path) -> None:
    _, prepared, profile = qa_bundle(tmp_path)
    executed = _execute(prepared, profile, SequencedBrowser((QAStatus.PASS,)))
    finding = QAFinding(
        "QFD-risk",
        prepared.candidate.canonical_fingerprint(),
        "risk",
        QASeverity.MINOR,
        QAFindingDisposition.OPEN,
        None,
        "Observed risk",
        (),
        (),
    )
    with pytest.raises(ValueError, match="authority"):
        replace(finding, disposition=QAFindingDisposition.ACCEPTED_RISK)
    accepted = replace(
        finding,
        disposition=QAFindingDisposition.ACCEPTED_RISK,
        authority_ref="reviewer:qa",
    )
    assert not accepted.blocking
    approval = EvidenceRef("approval:w08", "human-qa-approval", "urn:approval:w08")
    package = ReleaseReadinessPackage(
        CURRENT_WEB_CONTRACT_VERSION,
        "RRP-test",
        prepared.candidate.project_id,
        WebLifecycleStatus.TESTING,
        prepared.candidate.canonical_fingerprint(),
        prepared.candidate.source_tree_fingerprint,
        prepared.candidate.git_head,
        profile.canonical_fingerprint(),
        prepared.scope.canonical_fingerprint(),
        executed.preview.canonical_fingerprint(),
        executed.run.canonical_fingerprint(),
        executed.coverage.canonical_fingerprint(),
        tuple(item.fingerprint for item in executed.review.evidence_refs),
        (),
        ReconciliationStatus.CLEAN,
        approval,
    )
    assert decode_contract(ReleaseReadinessPackage, encode_contract(package)) == package
    with pytest.raises(ValueError, match="TESTING"):
        replace(package, runtime_state=WebLifecycleStatus.RELEASE_READY)
    blocker = replace(finding, severity=QASeverity.BLOCKER)
    with pytest.raises(ValueError, match="Blocking"):
        replace(package, findings=(blocker,))
    with pytest.raises(ValueError, match="reconciliation"):
        replace(package, reconciliation_status=ReconciliationStatus.REQUIRED)


def test_review_readiness_cannot_contradict_findings(tmp_path: Path) -> None:
    _, prepared, profile = qa_bundle(tmp_path)
    executed = _execute(prepared, profile, SequencedBrowser((QAStatus.PASS,)))
    with pytest.raises(ValueError, match="contradicts"):
        replace(executed.review, readiness=QAReadiness.BLOCKED)
    with pytest.raises(ValueError, match="approval"):
        replace(executed.review, readiness=QAReadiness.APPROVED)


def test_visual_evidence_never_claims_unapproved_pixel_baseline(tmp_path: Path) -> None:
    _, prepared, profile = qa_bundle(tmp_path)
    visual = _execute(prepared, profile, SequencedBrowser((QAStatus.PASS,))).visual
    assert visual.comparison is VisualComparisonDisposition.STRUCTURAL_ONLY
    with pytest.raises(ValueError, match="Structural-only"):
        replace(visual, baseline_fingerprint="sha256:baseline")
    with pytest.raises(ValueError, match="requires baseline"):
        replace(visual, comparison=VisualComparisonDisposition.BASELINE_MATCH)
