"""Deterministic structural audit adapters for rendered W08 evidence."""

from __future__ import annotations

from arch_web.application.architecture.planning import semantic_id
from arch_web.domain.qa import (
    AccessibilityQAEvidence,
    QACandidateBaseline,
    QARun,
    QAStatus,
    ResponsiveQAEvidence,
    VisualComparisonDisposition,
    VisualQAEvidence,
)


def _all(run: QARun, marker: str) -> bool:
    return bool(run.results) and all(
        item.status is QAStatus.PASS and f"{marker}:pass" in item.sanitized_diagnostics
        for item in run.results
    )


class StructuralAccessibilityAdapter:
    def audit(self, candidate: QACandidateBaseline, run: QARun) -> AccessibilityQAEvidence:
        passed = _all(run, "landmark") and _all(run, "focus")
        return AccessibilityQAEvidence(
            semantic_id("QEV", {"category": "accessibility", "run": run}),
            "accessibility-behavioral",
            candidate.canonical_fingerprint(),
            QAStatus.PASS if passed else QAStatus.FAIL,
            tuple(sorted({item.scenario_ref for item in run.results})),
            (
                "rendered landmark structure checked",
                "keyboard focus behavior checked",
                "not a WCAG certification",
            ),
            tuple(digest for item in run.results for digest in item.evidence_digests),
        )


class StructuralRuntimeObservationAdapter:
    def responsive_evidence(
        self, candidate: QACandidateBaseline, run: QARun
    ) -> ResponsiveQAEvidence:
        passed = _all(run, "overflow") and len({item.viewport_ref for item in run.results}) >= 2
        return ResponsiveQAEvidence(
            semantic_id("QEV", {"category": "responsive", "run": run}),
            "responsive-rendered",
            candidate.canonical_fingerprint(),
            QAStatus.PASS if passed else QAStatus.FAIL,
            tuple(sorted({item.viewport_ref for item in run.results})),
            ("overflow checked", "required interaction preserved across viewports"),
            tuple(digest for item in run.results for digest in item.evidence_digests),
        )


class StructuralVisualAdapter:
    """Uses W04 structure when no approved screenshot baseline exists."""

    def compare(self, candidate: QACandidateBaseline, run: QARun) -> VisualQAEvidence:
        passed = bool(run.results) and all(item.status is QAStatus.PASS for item in run.results)
        return VisualQAEvidence(
            semantic_id("QEV", {"category": "visual", "run": run}),
            "design-structural",
            candidate.canonical_fingerprint(),
            QAStatus.PASS if passed else QAStatus.FAIL,
            tuple(sorted({item.scenario_ref for item in run.results})),
            (
                "W04 structural contract evaluated",
                "screenshots retained only as local digests",
                "no approved pixel baseline; no pixel-match claim",
            ),
            tuple(digest for item in run.results for digest in item.evidence_digests),
            VisualComparisonDisposition.STRUCTURAL_ONLY,
        )


__all__ = (
    "StructuralAccessibilityAdapter",
    "StructuralRuntimeObservationAdapter",
    "StructuralVisualAdapter",
)
