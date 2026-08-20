"""Metamorphic W03 determinism and graph properties."""

from __future__ import annotations

from dataclasses import replace

import pytest
from hypothesis import given
from hypothesis import strategies as st

from arch_web import (
    ArchitecturePreparationError,
    ArchitectureReadiness,
    NavigationKind,
    NavigationModel,
    NavigationNode,
    NavigationVisibility,
    PrepareRequirementsCommand,
    WebContractValidationError,
    WebRoute,
    normalize_route_path,
    prepare_architecture,
    prepare_requirements,
)
from w02.factories import intake
from w03.factories import architecture_command


@given(
    st.lists(
        st.sampled_from(["about", "team", "products"]),
        min_size=1,
        max_size=3,
        unique=True,
    )
)
@pytest.mark.property
def test_route_normalization_is_idempotent(segments: list[str]) -> None:
    raw = "//" + "//".join(item.upper() for item in segments) + "//"
    normalized = normalize_route_path(raw)
    assert normalize_route_path(normalized) == normalized


@given(st.permutations((0, 1, 2, 3, 4, 5, 6)))
@pytest.mark.property
def test_requirement_order_does_not_change_architecture(order: tuple[int, ...]) -> None:
    base = intake(WebRoute.STANDARD)
    shuffled = replace(base, answers=tuple(base.answers[index] for index in order))
    prepared = prepare_requirements(PrepareRequirementsCommand(shuffled))
    command = architecture_command(
        WebRoute.STANDARD,
        requirements_contract=prepared.requirements_contract,
        requirements_review=prepared.review_package,
        approved_requirements_fingerprint=prepared.requirements_contract.canonical_fingerprint(),
        approved_requirements_review_fingerprint=prepared.review_package.canonical_fingerprint(),
    )
    assert (
        prepare_architecture(command).canonical_fingerprint()
        == prepare_architecture(architecture_command(WebRoute.STANDARD)).canonical_fingerprint()
    )


@given(st.integers(min_value=1, max_value=8))
@pytest.mark.property
def test_navigation_input_order_normalizes_deterministically(size: int) -> None:
    nodes = tuple(
        NavigationNode(
            f"node-{index}",
            f"surface-{index}",
            f"Node {index}",
            NavigationKind.PRIMARY,
            NavigationVisibility.PUBLIC,
            ("user",),
            index,
        )
        for index in range(size)
    )
    assert (
        NavigationModel("nav", "project", nodes).canonical_bytes()
        == NavigationModel("nav", "project", tuple(reversed(nodes))).canonical_bytes()
    )


@given(st.integers(min_value=2, max_value=6))
@pytest.mark.property
def test_any_parent_cycle_is_rejected(size: int) -> None:
    nodes = tuple(
        NavigationNode(
            f"node-{index}",
            f"surface-{index}",
            f"Node {index}",
            NavigationKind.PRIMARY,
            NavigationVisibility.PUBLIC,
            ("user",),
            index,
            parent_node_ref=f"node-{(index + 1) % size}",
        )
        for index in range(size)
    )
    with pytest.raises(WebContractValidationError, match="cycle"):
        NavigationModel("nav", "project", nodes)


def test_blockers_can_never_produce_ready_for_review() -> None:
    command = architecture_command()
    bad = replace(command, approved_requirements_fingerprint="0" * 64)
    with pytest.raises(ArchitecturePreparationError, match="fingerprint"):
        prepare_architecture(bad)
    assert (
        prepare_architecture(command).review_package.readiness
        is ArchitectureReadiness.READY_FOR_REVIEW
    )
