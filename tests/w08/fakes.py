"""Bounded W08 test doubles for evidence aggregation."""

from __future__ import annotations

from dataclasses import replace

from arch_web import (
    IntegrationQAEvidence,
    PreviewEnvironmentEvidence,
    PreviewPlan,
    QACandidateBaseline,
    QAResult,
    QAScenario,
    QAStatus,
    ViewportSpec,
)
from arch_web.application.architecture.planning import semantic_id


class FakePreviewSession:
    def __init__(self, evidence: PreviewEnvironmentEvidence) -> None:
        self._evidence = evidence

    @property
    def evidence(self) -> PreviewEnvironmentEvidence:
        return self._evidence

    def stop(self) -> PreviewEnvironmentEvidence:
        self._evidence = replace(self._evidence, cleanup_verified=True)
        return self._evidence


class FakePreviewAdapter:
    identity = "fake-preview@0.1.0"

    def __init__(self, *, ready: bool = True) -> None:
        self.ready = ready

    def start(self, plan: PreviewPlan) -> FakePreviewSession:
        return FakePreviewSession(
            PreviewEnvironmentEvidence(
                "PVE-fake",
                plan.candidate_fingerprint,
                "http://127.0.0.1:9000/",
                "fake-preview@0.1.0",
                1,
                "sha256:fixture",
                self.ready,
                "sha256:log",
                False,
            )
        )


class FakeIntegrationAdapter:
    def __init__(self, status: QAStatus = QAStatus.PASS) -> None:
        self.status = status

    def audit(self, candidate: QACandidateBaseline, run: object) -> IntegrationQAEvidence:
        return IntegrationQAEvidence(
            "QEV-fake-integration",
            "integration-fake",
            candidate.canonical_fingerprint(),
            self.status,
            ("scenario",),
            ("synthetic integration evidence",),
            ("sha256:integration",),
        )


class SequencedBrowser:
    identity = "fake-chromium@0.1.0"
    available = True

    def __init__(self, statuses: tuple[QAStatus, ...], *, stale: bool = False) -> None:
        self.statuses = statuses
        self.stale = stale
        self.calls = 0

    def execute(
        self,
        scenario: QAScenario,
        candidate: QACandidateBaseline,
        endpoint: str,
        viewport: ViewportSpec,
    ) -> QAResult:
        del endpoint
        status = self.statuses[min(self.calls, len(self.statuses) - 1)]
        self.calls += 1
        fingerprint = candidate.canonical_fingerprint()
        if self.stale:
            fingerprint = "sha256:stale"
        return QAResult(
            semantic_id(
                "QRS",
                {
                    "scenario": scenario.scenario_id,
                    "viewport": viewport.viewport_id,
                    "call": self.calls,
                },
            ),
            scenario.scenario_id,
            fingerprint,
            candidate.source_tree_fingerprint,
            candidate.git_head,
            "fake-chromium/1",
            viewport.viewport_id,
            status,
            (status,),
            7 if status is QAStatus.PASS else 0,
            (f"sha256:evidence-{self.calls}",),
            (
                "external_requests:pass",
                "focus:pass",
                "landmark:pass",
                "overflow:pass",
                "runtime_errors:pass",
            ),
        )


__all__ = (
    "FakeIntegrationAdapter",
    "FakePreviewAdapter",
    "FakePreviewSession",
    "SequencedBrowser",
)
