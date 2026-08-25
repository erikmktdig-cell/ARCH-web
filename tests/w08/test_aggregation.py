"""Blocking, inconclusive, flaky, stale, and cleanup W08 semantics."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from arch_web import (
    ExecuteQACommand,
    ExecuteQAResult,
    PrepareQAResult,
    QABaselineProfile,
    QAExecutionAuthorization,
    QAExecutionError,
    QAReadiness,
    QASeverity,
    QAStatus,
    StructuralAccessibilityAdapter,
    StructuralRuntimeObservationAdapter,
    StructuralVisualAdapter,
    WebLifecycleStatus,
    execute_qa,
)
from arch_web.contracts.versions import CURRENT_WEB_CONTRACT_VERSION
from arch_web.ports.qa import IntegrationAuditPort
from w08.factories import qa_bundle
from w08.fakes import FakeIntegrationAdapter, FakePreviewAdapter, SequencedBrowser


def _authorization(prepared: PrepareQAResult) -> QAExecutionAuthorization:
    candidate = prepared.candidate
    scope = prepared.scope
    return QAExecutionAuthorization(
        CURRENT_WEB_CONTRACT_VERSION,
        "QAU-aggregate",
        candidate.project_id,
        candidate.canonical_fingerprint(),
        scope.canonical_fingerprint(),
        candidate.qa_profile_fingerprint,
        WebLifecycleStatus.TESTING,
        True,
    )


def _execute(
    prepared: PrepareQAResult,
    profile: QABaselineProfile,
    browser: SequencedBrowser,
    integration: IntegrationAuditPort | None = None,
) -> ExecuteQAResult:
    return execute_qa(
        ExecuteQACommand(
            WebLifecycleStatus.TESTING,
            prepared,
            profile,
            _authorization(prepared),
            "2026-08-22T12:00:00Z",
            "2026-08-22T12:00:10Z",
        ),
        FakePreviewAdapter(),
        browser,
        integration or FakeIntegrationAdapter(),
        StructuralAccessibilityAdapter(),
        StructuralVisualAdapter(),
        StructuralRuntimeObservationAdapter(),
    )


@pytest.mark.parametrize("status", [QAStatus.FAIL, QAStatus.INCONCLUSIVE])
def test_nonpassing_evidence_blocks_review(tmp_path: Path, status: QAStatus) -> None:
    _, prepared, profile = qa_bundle(tmp_path)
    result = _execute(prepared, profile, SequencedBrowser((status,)))
    assert result.review.readiness is QAReadiness.BLOCKED
    assert result.findings
    assert any(item.severity is QASeverity.MAJOR for item in result.findings)


def test_inconsistent_bounded_retry_remains_flaky(tmp_path: Path) -> None:
    _, prepared, profile = qa_bundle(tmp_path)
    scenarios = tuple(replace(item, retry_limit=1) for item in prepared.scope.scenarios)
    prepared = replace(prepared, scope=replace(prepared.scope, scenarios=scenarios))
    browser = SequencedBrowser((QAStatus.FAIL, QAStatus.PASS, QAStatus.FAIL, QAStatus.PASS))
    result = _execute(prepared, profile, browser)
    assert {item.status for item in result.run.results} == {QAStatus.FLAKY}
    assert all(
        item.attempt_statuses == (QAStatus.FAIL, QAStatus.PASS) for item in result.run.results
    )
    assert result.review.readiness is QAReadiness.BLOCKED


def test_stale_browser_evidence_is_rejected(tmp_path: Path) -> None:
    _, prepared, profile = qa_bundle(tmp_path)
    with pytest.raises(QAExecutionError, match="exact QA candidate"):
        _execute(prepared, profile, SequencedBrowser((QAStatus.PASS,), stale=True))


def test_backend_integration_failure_blocks_security_and_review(tmp_path: Path) -> None:
    _, prepared, profile = qa_bundle(tmp_path)
    result = _execute(
        prepared,
        profile,
        SequencedBrowser((QAStatus.PASS,)),
        FakeIntegrationAdapter(QAStatus.FAIL),
    )
    assert result.integration.status is QAStatus.FAIL
    assert result.security.status is QAStatus.FAIL
    assert result.review.readiness is QAReadiness.BLOCKED


def test_unready_preview_never_launches_browser(tmp_path: Path) -> None:
    _, prepared, profile = qa_bundle(tmp_path)
    browser = SequencedBrowser((QAStatus.PASS,))
    command = ExecuteQACommand(
        WebLifecycleStatus.TESTING,
        prepared,
        profile,
        _authorization(prepared),
        "2026-08-22T12:00:00Z",
        "2026-08-22T12:00:10Z",
    )
    with pytest.raises(QAExecutionError, match="ready"):
        execute_qa(
            command,
            FakePreviewAdapter(ready=False),
            browser,
            FakeIntegrationAdapter(),
            StructuralAccessibilityAdapter(),
            StructuralVisualAdapter(),
            StructuralRuntimeObservationAdapter(),
        )
    assert browser.calls == 0
