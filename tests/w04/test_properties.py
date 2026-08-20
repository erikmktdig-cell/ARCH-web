"""W04 property and metamorphic determinism tests."""

from __future__ import annotations

from dataclasses import replace

import pytest
from hypothesis import given
from hypothesis import strategies as st

from arch_web import (
    ComponentStateName,
    PrimitiveToken,
    PrimitiveTokenKind,
    PrimitiveTokenSet,
    UIReadiness,
    prepare_ui_specification,
)
from arch_web.application.design.tokens import contrast_ratio, normalize_color
from w04.factories import design_command


@given(st.integers(min_value=0, max_value=0xFFFFFF))
@pytest.mark.property
def test_contrast_is_symmetric_and_identity_is_one(value: int) -> None:
    color = f"#{value:06X}"
    assert contrast_ratio(color, color) == pytest.approx(1.0)
    assert contrast_ratio(color, "#FFFFFF") == pytest.approx(contrast_ratio("#FFFFFF", color))


@given(st.text(alphabet="0123456789abcdefABCDEF", min_size=6, max_size=6))
@pytest.mark.property
def test_color_normalization_is_idempotent(value: str) -> None:
    normalized = normalize_color(value)
    assert normalize_color(normalized) == normalized


@given(st.permutations((0, 1, 2, 3)))
@pytest.mark.property
def test_primitive_order_does_not_change_bytes(order: tuple[int, ...]) -> None:
    tokens = tuple(
        PrimitiveToken(f"space.{index}", PrimitiveTokenKind.SPACING, f"{index + 1}px")
        for index in range(4)
    )
    first = PrimitiveTokenSet("tokens", tokens)
    shuffled = PrimitiveTokenSet("tokens", tuple(tokens[index] for index in order))
    assert first.canonical_bytes() == shuffled.canonical_bytes()


@given(
    st.permutations(
        (
            ComponentStateName.DEFAULT,
            ComponentStateName.FOCUS_VISIBLE,
            ComponentStateName.DISABLED,
            ComponentStateName.ERROR,
        )
    )
)
@pytest.mark.property
def test_component_state_order_is_canonical(order: tuple[ComponentStateName, ...]) -> None:
    result = prepare_ui_specification(design_command())
    component = result.ui_specification.components[0]
    available = {item.state: item for item in component.states}
    selected = tuple(available[item] for item in order if item in available)
    assert (
        replace(component, states=selected).canonical_bytes()
        == replace(component, states=tuple(reversed(selected))).canonical_bytes()
    )


@given(st.permutations((0, 1, 2)))
@pytest.mark.property
def test_responsive_rule_order_is_canonical(order: tuple[int, ...]) -> None:
    design = prepare_ui_specification(design_command()).design_system
    policy = design.responsive
    rules = policy.rules[:3]
    changed = replace(policy, rules=tuple(rules[index] for index in order))
    assert changed.canonical_bytes() == replace(policy, rules=rules).canonical_bytes()


def test_any_blocking_profile_gap_never_yields_ready() -> None:
    result = prepare_ui_specification(design_command(adopt_profile=False))
    assert any(item.blocking for item in result.review_package.findings)
    assert result.review_package.readiness is UIReadiness.NOT_READY
