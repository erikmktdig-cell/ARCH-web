"""W08 candidate, real preview, browser, and QA aggregation tests."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from pathlib import Path

import pytest

from arch_web import (
    ExecuteQACommand,
    LocalBackendIntegrationAdapter,
    LocalChromiumAdapter,
    LocalPreviewAdapter,
    PrepareQACommand,
    PrepareQAResult,
    QACoverageDisposition,
    QAExecutionAuthorization,
    QAExecutionError,
    QAPreparationError,
    QAReadiness,
    QAStatus,
    StructuralAccessibilityAdapter,
    StructuralRuntimeObservationAdapter,
    StructuralVisualAdapter,
    WebLifecycleStatus,
    execute_qa,
    prepare_qa,
)
from arch_web.contracts.versions import CURRENT_WEB_CONTRACT_VERSION
from w08.factories import qa_bundle, stale_baseline


def _authorization(prepared: PrepareQAResult) -> QAExecutionAuthorization:
    candidate = prepared.candidate
    scope = prepared.scope
    return QAExecutionAuthorization(
        CURRENT_WEB_CONTRACT_VERSION,
        "QAU-test",
        candidate.project_id,
        candidate.canonical_fingerprint(),
        scope.canonical_fingerprint(),
        candidate.qa_profile_fingerprint,
        WebLifecycleStatus.TESTING,
        True,
    )


def test_candidate_scope_and_preview_are_deterministic(tmp_path: Path) -> None:
    command, prepared, profile = qa_bundle(tmp_path)
    assert prepare_qa(command) == prepared
    assert prepared.candidate.source_tree_fingerprint == command.current_baseline.tree_fingerprint
    assert prepared.candidate.git_head == command.current_baseline.repository.head
    assert prepared.scope.profile_fingerprint == profile.canonical_fingerprint()
    assert (
        prepared.preview_plan.application_database_path
        != prepared.preview_plan.runtime_database_path
    )
    assert all(scenario.steps for scenario in prepared.scope.scenarios)


@pytest.mark.parametrize(
    "mutation",
    [
        lambda command: stale_baseline(command),
        lambda command: replace(command, project_status=WebLifecycleStatus.TESTING),
        lambda command: replace(command, requirements_fingerprint="sha256:stale"),
        lambda command: replace(command, profile=replace(command.profile, adopted=False)),
    ],
)
def test_stale_or_unapproved_candidate_fails_closed(
    tmp_path: Path, mutation: Callable[[PrepareQACommand], PrepareQACommand]
) -> None:
    command, _, _ = qa_bundle(tmp_path)
    with pytest.raises(QAPreparationError):
        prepare_qa(mutation(command))


def test_real_local_preview_and_headless_browser_vertical_slice(tmp_path: Path) -> None:
    _, prepared, profile = qa_bundle(tmp_path)
    browser = LocalChromiumAdapter()
    if not browser.available:
        pytest.skip("No locally provisioned Chromium browser")
    result = execute_qa(
        ExecuteQACommand(
            WebLifecycleStatus.TESTING,
            prepared,
            profile,
            _authorization(prepared),
            "2026-08-22T12:00:00Z",
            "2026-08-22T12:00:10Z",
        ),
        LocalPreviewAdapter(),
        browser,
        LocalBackendIntegrationAdapter(
            tmp_path,
            "src/backend/service.py",
            "src/backend/schema.sql",
            tmp_path / "application.sqlite",
            tmp_path / "runtime.sqlite",
        ),
        StructuralAccessibilityAdapter(),
        StructuralVisualAdapter(),
        StructuralRuntimeObservationAdapter(),
    )
    assert result.preview.ready
    assert result.preview.cleanup_verified
    assert result.run.results
    assert {item.status for item in result.run.results} == {QAStatus.PASS}
    assert result.accessibility.status is QAStatus.PASS
    assert result.integration.status is QAStatus.PASS
    assert result.responsive.status is QAStatus.PASS
    assert result.visual.status is QAStatus.PASS
    assert all(item.disposition is QACoverageDisposition.TESTED for item in result.coverage.items)
    assert result.findings == ()
    assert result.review.readiness is QAReadiness.READY_FOR_REVIEW
    assert not (tmp_path / "application.sqlite").exists()
    assert not (tmp_path / "runtime.sqlite").exists()


def test_execute_rejects_wrong_state_authorization_and_profile(tmp_path: Path) -> None:
    _, prepared, profile = qa_bundle(tmp_path)
    base = ExecuteQACommand(
        WebLifecycleStatus.TESTING,
        prepared,
        profile,
        _authorization(prepared),
        "2026-08-22T12:00:00Z",
        "2026-08-22T12:00:10Z",
    )
    adapters = (
        LocalPreviewAdapter(),
        LocalChromiumAdapter(),
        LocalBackendIntegrationAdapter(
            tmp_path,
            "src/backend/service.py",
            "src/backend/schema.sql",
            tmp_path / "application.sqlite",
            tmp_path / "runtime.sqlite",
        ),
        StructuralAccessibilityAdapter(),
        StructuralVisualAdapter(),
        StructuralRuntimeObservationAdapter(),
    )
    with pytest.raises(QAExecutionError, match="TESTING"):
        execute_qa(replace(base, project_status=WebLifecycleStatus.IMPLEMENTING), *adapters)
    with pytest.raises(QAExecutionError, match="authorization"):
        execute_qa(
            replace(base, authorization=replace(base.authorization, authorized=False)), *adapters
        )
    with pytest.raises(QAExecutionError, match="profile"):
        execute_qa(replace(base, profile=replace(profile, profile_id="other")), *adapters)


def test_preview_rejects_missing_or_escaping_entrypoint(tmp_path: Path) -> None:
    _, prepared, _ = qa_bundle(tmp_path)
    adapter = LocalPreviewAdapter()
    with pytest.raises(QAExecutionError, match="entrypoint"):
        adapter.start(replace(prepared.preview_plan, entrypoint_path="missing.html"))
    outside = tmp_path.parent / "outside-w08.html"
    outside.write_text("<!doctype html>", encoding="utf-8")
    with pytest.raises(QAExecutionError, match="entrypoint"):
        adapter.start(replace(prepared.preview_plan, entrypoint_path=str(outside)))


def test_preview_cleanup_is_idempotent(tmp_path: Path) -> None:
    _, prepared, _ = qa_bundle(tmp_path)
    session = LocalPreviewAdapter().start(prepared.preview_plan)
    assert session.evidence.ready
    assert not session.evidence.cleanup_verified
    assert session.stop().cleanup_verified
    assert session.stop().cleanup_verified
