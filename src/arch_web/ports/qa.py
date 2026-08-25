"""Framework-neutral W08 preview, browser, and audit boundaries."""

from __future__ import annotations

from typing import Protocol

from arch_web.domain.qa import (
    AccessibilityQAEvidence,
    IntegrationQAEvidence,
    PreviewEnvironmentEvidence,
    PreviewPlan,
    QACandidateBaseline,
    QAResult,
    QARun,
    QAScenario,
    ResponsiveQAEvidence,
    ViewportSpec,
    VisualQAEvidence,
)


class PreviewSessionPort(Protocol):
    @property
    def evidence(self) -> PreviewEnvironmentEvidence: ...

    def stop(self) -> PreviewEnvironmentEvidence: ...


class PreviewRuntimePort(Protocol):
    @property
    def identity(self) -> str: ...

    def start(self, plan: PreviewPlan) -> PreviewSessionPort: ...


class BrowserAutomationPort(Protocol):
    @property
    def identity(self) -> str: ...

    @property
    def available(self) -> bool: ...

    def execute(
        self,
        scenario: QAScenario,
        candidate: QACandidateBaseline,
        endpoint: str,
        viewport: ViewportSpec,
    ) -> QAResult: ...


class AccessibilityAuditPort(Protocol):
    def audit(self, candidate: QACandidateBaseline, run: QARun) -> AccessibilityQAEvidence: ...


class IntegrationAuditPort(Protocol):
    def audit(self, candidate: QACandidateBaseline, run: QARun) -> IntegrationQAEvidence: ...


class VisualComparisonPort(Protocol):
    def compare(self, candidate: QACandidateBaseline, run: QARun) -> VisualQAEvidence: ...


class RuntimeObservationPort(Protocol):
    def responsive_evidence(
        self, candidate: QACandidateBaseline, run: QARun
    ) -> ResponsiveQAEvidence: ...


__all__ = (
    "AccessibilityAuditPort",
    "BrowserAutomationPort",
    "IntegrationAuditPort",
    "PreviewRuntimePort",
    "PreviewSessionPort",
    "RuntimeObservationPort",
    "VisualComparisonPort",
)
