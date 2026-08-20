"""Deterministic token construction and color contrast evaluation."""

from __future__ import annotations

import re

from arch_web.application.architecture.planning import semantic_id
from arch_web.contracts.versions import CURRENT_WEB_CONTRACT_VERSION
from arch_web.domain.design_intent import ReferenceDesignProfile
from arch_web.domain.design_tokens import (
    PrimitiveToken,
    PrimitiveTokenKind,
    PrimitiveTokenSet,
    SemanticToken,
    SemanticTokenSet,
)
from arch_web.domain.references import ContractRef

_COLOR_INPUT = re.compile(r"^#?([0-9a-fA-F]{6})$")


def normalize_color(value: str) -> str:
    match = _COLOR_INPUT.fullmatch(value.strip())
    if match is None:
        raise ValueError("Color must contain exactly six hexadecimal digits")
    return f"#{match.group(1).upper()}"


def _linear(channel: int) -> float:
    value = channel / 255
    return value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055) ** 2.4


def relative_luminance(color: str) -> float:
    canonical = normalize_color(color)
    channels = tuple(int(canonical[index : index + 2], 16) for index in (1, 3, 5))
    red, green, blue = (_linear(item) for item in channels)
    return 0.2126 * red + 0.7152 * green + 0.0722 * blue


def contrast_ratio(foreground: str, background: str) -> float:
    first, second = relative_luminance(foreground), relative_luminance(background)
    lighter, darker = max(first, second), min(first, second)
    return (lighter + 0.05) / (darker + 0.05)


def build_token_sets(
    profile: ReferenceDesignProfile | None,
    overrides: tuple[PrimitiveToken, ...],
) -> tuple[PrimitiveTokenSet, SemanticTokenSet]:
    primitives: dict[str, PrimitiveToken] = {}
    semantics: tuple[SemanticToken, ...] = ()
    if profile is not None:
        primitives = {
            token_id: PrimitiveToken(token_id, PrimitiveTokenKind(kind), value)
            for token_id, kind, value in profile.primitive_tokens
        }
        semantics = tuple(SemanticToken(role, target) for role, target in profile.semantic_tokens)
    for override in overrides:
        primitives[override.token_id] = override
    primitive_values = tuple(primitives.values())
    primitive_set = PrimitiveTokenSet(semantic_id("PTS", primitive_values), primitive_values)
    primitive_ref = ContractRef(
        target_contract_type=primitive_set.contract_type,
        contract_id=primitive_set.token_set_id,
        contract_version=CURRENT_WEB_CONTRACT_VERSION,
        fingerprint=primitive_set.canonical_fingerprint(),
    )
    semantic_set = SemanticTokenSet(
        semantic_id(
            "STS",
            {"primitive": primitive_set.canonical_fingerprint(), "tokens": semantics},
        ),
        primitive_ref,
        semantics,
    )
    return primitive_set, semantic_set


def resolved_color_roles(
    primitives: PrimitiveTokenSet, semantics: SemanticTokenSet
) -> dict[str, str]:
    return {
        role: token.value
        for role, token in semantics.resolve(primitives)
        if token.kind is PrimitiveTokenKind.COLOR
    }


__all__ = ("build_token_sets", "contrast_ratio", "normalize_color", "relative_luminance")
