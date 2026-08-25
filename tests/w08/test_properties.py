"""Property tests for deterministic W08 normalization and coverage semantics."""

from __future__ import annotations

import pytest
from hypothesis import given
from hypothesis import strategies as st

from arch_web import (
    BrowserSupportPolicy,
    QACoverageDisposition,
    QACoverageItem,
    QACoverageMatrix,
    QAResult,
    QAStatus,
    ViewportPolicy,
    ViewportSpec,
)


@given(st.permutations(("chromium", "webkit")))
def test_browser_policy_canonicalizes_explicit_engine_order(order: list[str]) -> None:
    versions = {"chromium": "151", "webkit": "26"}
    policy = BrowserSupportPolicy(
        "browser-matrix",
        tuple(order),
        tuple(versions[item] for item in order),
        True,
    )
    assert policy.engines == ("chromium", "webkit")
    assert policy.browser_versions == ("151", "26")


@given(st.permutations(("desktop", "mobile", "tablet")))
def test_viewport_policy_has_stable_order(order: list[str]) -> None:
    widths = {"desktop": 1280, "mobile": 390, "tablet": 768}
    policy = ViewportPolicy(
        "viewports",
        tuple(ViewportSpec(item, widths[item], 800, item == "mobile") for item in order),
        (1024, 720, 720),
    )
    assert tuple(item.viewport_id for item in policy.viewports) == (
        "desktop",
        "mobile",
        "tablet",
    )
    assert policy.breakpoint_boundaries == (720, 1024)


@given(st.permutations(("REQ-a", "REQ-b", "REQ-c")))
def test_coverage_matrix_fingerprint_is_permutation_invariant(order: list[str]) -> None:
    items = tuple(
        QACoverageItem(
            item,
            QACoverageDisposition.TESTED,
            ("scenario",),
            ("evidence",),
            "covered",
            True,
        )
        for item in order
    )
    matrix = QACoverageMatrix("matrix", "sha256:candidate", items)
    canonical = QACoverageMatrix("matrix", "sha256:candidate", tuple(reversed(items)))
    assert matrix == canonical
    assert matrix.canonical_fingerprint() == canonical.canonical_fingerprint()


@given(
    st.lists(
        st.sampled_from((QAStatus.PASS, QAStatus.FAIL, QAStatus.INCONCLUSIVE)),
        min_size=1,
        max_size=3,
    )
)
def test_inconsistent_attempts_can_only_be_flaky(attempts: list[QAStatus]) -> None:
    values = (
        "result",
        "scenario",
        "sha256:candidate",
        "sha256:tree",
        "f" * 40,
        "chromium/151",
        "desktop",
        attempts[-1],
        tuple(attempts),
        1,
        (),
        (),
    )
    if len(set(attempts)) > 1:
        with pytest.raises(ValueError, match="FLAKY"):
            QAResult(*values)
    else:
        base = QAResult(*values)
        assert base.attempt_statuses == tuple(attempts)
