"""Negative adapter behavior, cleanup, and explicit tool-unavailability tests."""

from __future__ import annotations

import urllib.request
from pathlib import Path

import pytest

from arch_web import (
    LocalBackendIntegrationAdapter,
    LocalChromiumAdapter,
    LocalPreviewAdapter,
    QAStatus,
)
from arch_web.adapters.qa import chromium
from w08.factories import qa_bundle
from w08.fakes import SequencedBrowser
from w08.test_aggregation import _execute


def test_backend_adapter_fails_closed_for_database_alias_and_missing_artifact(
    tmp_path: Path,
) -> None:
    _, prepared, profile = qa_bundle(tmp_path)
    run = _execute(prepared, profile, SequencedBrowser((QAStatus.PASS,))).run
    same = tmp_path / "same.sqlite"
    aliased = LocalBackendIntegrationAdapter(
        tmp_path,
        "src/backend/service.py",
        "src/backend/schema.sql",
        same,
        same,
    ).audit(prepared.candidate, run)
    assert aliased.status is QAStatus.FAIL
    assert "integration_failure:ValueError" in aliased.observations
    missing = LocalBackendIntegrationAdapter(
        tmp_path,
        "src/backend/missing.py",
        "src/backend/schema.sql",
        tmp_path / "application.sqlite",
        tmp_path / "runtime.sqlite",
    ).audit(prepared.candidate, run)
    assert missing.status is QAStatus.FAIL
    assert "integration_failure:FileNotFoundError" in missing.observations
    assert not (tmp_path / "application.sqlite").exists()


def test_browser_unavailability_is_explicit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, prepared, profile = qa_bundle(tmp_path)
    monkeypatch.setattr(chromium, "_browser_path", lambda: None)
    adapter = LocalChromiumAdapter()
    assert not adapter.available
    scenario = prepared.scope.scenarios[0]
    result = adapter.execute(
        scenario,
        prepared.candidate,
        "http://127.0.0.1:9000/",
        profile.viewport_policy.viewports[0],
    )
    assert result.status is QAStatus.INCONCLUSIVE
    assert result.sanitized_diagnostics == ("browser_tool_unavailable",)


def test_browser_rejects_non_loopback_endpoint(tmp_path: Path) -> None:
    _, prepared, profile = qa_bundle(tmp_path)
    adapter = LocalChromiumAdapter()
    if not adapter.available:
        pytest.skip("No locally provisioned Chromium browser")
    with pytest.raises(ValueError, match="loopback"):
        adapter.execute(
            prepared.scope.scenarios[0],
            prepared.candidate,
            "https://example.invalid/",
            profile.viewport_policy.viewports[0],
        )


def test_preview_readiness_failure_still_cleans_up(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, prepared, _ = qa_bundle(tmp_path)

    def unavailable(*_args: object, **_kwargs: object) -> object:
        raise OSError("readiness unavailable")

    monkeypatch.setattr(urllib.request, "urlopen", unavailable)
    session = LocalPreviewAdapter().start(prepared.preview_plan)
    assert not session.evidence.ready
    assert session.stop().cleanup_verified
