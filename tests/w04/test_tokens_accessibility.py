"""Token, color, typography, motion, and responsive contract tests."""

from __future__ import annotations

from dataclasses import replace

import pytest

from arch_web import (
    BreakpointSpec,
    ContractRef,
    MotionPolicy,
    MotionPurpose,
    MotionSpec,
    PrimitiveToken,
    PrimitiveTokenKind,
    PrimitiveTokenSet,
    ResponsiveBehavior,
    ResponsivePolicy,
    ResponsiveRule,
    SemanticToken,
    SemanticTokenSet,
    TypographyRole,
    TypographySystem,
    WebContractReferenceError,
    WebContractValidationError,
)
from arch_web.application.design.tokens import (
    contrast_ratio,
    normalize_color,
    relative_luminance,
)


def primitive_set(*tokens: PrimitiveToken) -> PrimitiveTokenSet:
    return PrimitiveTokenSet("primitive-test", tokens)


def semantic_set(primitives: PrimitiveTokenSet, *tokens: SemanticToken) -> SemanticTokenSet:
    return SemanticTokenSet(
        "semantic-test",
        ContractRef(
            primitives.contract_type,
            primitives.token_set_id,
            "0.1.0",
            primitives.canonical_fingerprint(),
        ),
        tokens,
    )


@pytest.mark.parametrize(
    ("raw", "canonical"),
    [("#ffffff", "#FFFFFF"), ("005fcc", "#005FCC"), ("#Ab12eF", "#AB12EF")],
)
def test_color_normalization_is_canonical(raw: str, canonical: str) -> None:
    assert normalize_color(raw) == canonical


@pytest.mark.parametrize("raw", ["#fff", "#FFFFFFFF", "red", "#GG0000", ""])
def test_color_parser_rejects_malformed_or_alpha_values(raw: str) -> None:
    with pytest.raises(ValueError, match="six hexadecimal"):
        normalize_color(raw)


def test_known_contrast_pairs_and_luminance() -> None:
    assert contrast_ratio("#000000", "#FFFFFF") == pytest.approx(21.0)
    assert contrast_ratio("#777777", "#FFFFFF") == pytest.approx(4.478, rel=1e-3)
    assert relative_luminance("#000000") == 0.0
    assert relative_luminance("#FFFFFF") == 1.0


def test_primitive_color_requires_canonical_representation() -> None:
    with pytest.raises(WebContractValidationError, match="canonical"):
        PrimitiveToken("color.bad", PrimitiveTokenKind.COLOR, "#ffffff")
    with pytest.raises(WebContractValidationError, match="dotted"):
        PrimitiveToken("Bad Token", PrimitiveTokenKind.SPACING, "8px")


def test_primitive_and_semantic_order_are_canonical() -> None:
    first = PrimitiveToken("color.first", PrimitiveTokenKind.COLOR, "#000000")
    second = PrimitiveToken("color.second", PrimitiveTokenKind.COLOR, "#FFFFFF")
    primitives = primitive_set(second, first)
    assert [item.token_id for item in primitives.tokens] == ["color.first", "color.second"]
    semantics = semantic_set(
        primitives,
        SemanticToken("text.secondary", "color.second"),
        SemanticToken("text.primary", "color.first"),
    )
    assert [item.role for item in semantics.tokens] == ["text.primary", "text.secondary"]


def test_semantic_alias_resolution_and_cycle_detection() -> None:
    color = PrimitiveToken("color.ink", PrimitiveTokenKind.COLOR, "#111111")
    primitives = primitive_set(color)
    aliases = semantic_set(
        primitives,
        SemanticToken("text.base", "color.ink"),
        SemanticToken("text.primary", "text.base"),
    )
    assert aliases.resolve(primitives) == (("text.base", color), ("text.primary", color))
    cycle = semantic_set(
        primitives,
        SemanticToken("text.base", "text.primary"),
        SemanticToken("text.primary", "text.base"),
    )
    with pytest.raises(WebContractValidationError, match="cycle"):
        cycle.resolve(primitives)


def test_semantic_missing_target_and_wrong_primitive_ref_fail_closed() -> None:
    color = PrimitiveToken("color.ink", PrimitiveTokenKind.COLOR, "#111111")
    primitives = primitive_set(color)
    missing = semantic_set(primitives, SemanticToken("text.primary", "color.missing"))
    with pytest.raises(WebContractReferenceError, match="Unresolved"):
        missing.resolve(primitives)
    wrong = replace(missing.primitive_set_ref, fingerprint="0" * 64)
    with pytest.raises(WebContractReferenceError, match="fingerprint"):
        replace(missing, primitive_set_ref=wrong).resolve(primitives)


def test_duplicate_token_roles_fail() -> None:
    token = PrimitiveToken("space.2", PrimitiveTokenKind.SPACING, "8px")
    with pytest.raises(WebContractValidationError, match="unique"):
        primitive_set(token, token)
    primitives = primitive_set(token)
    semantic = SemanticToken("layout.gap", "space.2")
    with pytest.raises(WebContractValidationError, match="unique"):
        semantic_set(primitives, semantic, semantic)


def test_typography_requires_body_and_valid_metrics() -> None:
    body = TypographyRole(
        "body", "font.family.body", "font.size.body", "font.weight.regular", 1.5, 2
    )
    heading = TypographyRole(
        "heading", "font.family.body", "font.size.heading", "font.weight.strong", 1.2, 1
    )
    system = TypographySystem("type", (body, heading), "45-75 characters")
    assert [item.role for item in system.roles] == ["heading", "body"]
    with pytest.raises(WebContractValidationError, match="body"):
        TypographySystem("type", (heading,), "measure")
    with pytest.raises(WebContractValidationError, match="line height"):
        replace(body, line_height_ratio=0.9)


def test_responsive_policy_validates_ranges_refs_and_actions() -> None:
    narrow = BreakpointSpec("narrow", 0, 599)
    rule = ResponsiveRule("rule", "narrow", ResponsiveBehavior.REFLOW, ("surface",), "reflow")
    policy = ResponsivePolicy("responsive", (narrow,), (rule,), "reflow", 44)
    assert policy.rules == (rule,)
    with pytest.raises(WebContractValidationError, match="range"):
        BreakpointSpec("bad", 600, 599)
    with pytest.raises(WebContractReferenceError, match="breakpoint"):
        replace(policy, rules=(replace(rule, breakpoint_ref="missing"),))
    with pytest.raises(WebContractValidationError, match="24"):
        replace(policy, touch_target_minimum=20)


def test_motion_requires_purpose_and_reduced_motion() -> None:
    with pytest.raises(WebContractValidationError, match="reduced-motion"):
        MotionSpec(
            "motion", MotionPurpose.EMPHASIS, "motion.fast", "motion.ease", "load", "hero", None
        )
    motion = MotionSpec(
        "motion",
        MotionPurpose.FEEDBACK,
        "motion.fast",
        "motion.ease",
        "result",
        "status",
        "instant state",
    )
    with pytest.raises(WebContractValidationError, match="autoplay"):
        MotionPolicy("policy", (motion,), True)
    with pytest.raises(WebContractValidationError, match="unique"):
        MotionPolicy("policy", (motion, motion))
