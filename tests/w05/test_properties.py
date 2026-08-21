"""W05 property and metamorphic guarantees."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from hypothesis import given
from hypothesis import strategies as st

from arch_web import WebRoute, WorkspaceReadiness, prepare_workspace
from arch_web.workspace_paths import normalize_managed_path
from w05.factories import workspace_command


@given(order=st.permutations((0, 1, 2)))
def test_plan_unit_order_is_canonical(order: tuple[int, ...]) -> None:
    plan = prepare_workspace(
        workspace_command(Path("C:/arch-w05-property"), WebRoute.STANDARD)
    ).plan
    units = plan.units[:3]
    changed = replace(plan, units=tuple(units[index] for index in order) + plan.units[3:])
    assert changed.canonical_bytes() == plan.canonical_bytes()


@given(st.text(alphabet="abcdefghijklmnopqrstuvwxyz0123456789_-", min_size=1, max_size=20))
def test_single_safe_segment_is_stable(segment: str) -> None:
    assert normalize_managed_path(segment) == segment


def test_dirty_baseline_never_becomes_ready(tmp_path: Path) -> None:
    command = workspace_command(tmp_path)
    dirty = replace(command.baseline.repository, present=True, dirty_paths=("user.txt",))
    result = prepare_workspace(
        replace(command, baseline=replace(command.baseline, repository=dirty))
    )
    assert result.review.readiness is WorkspaceReadiness.NOT_READY
