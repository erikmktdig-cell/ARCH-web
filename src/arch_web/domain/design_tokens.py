"""Primitive and semantic design-token contracts."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum, unique

from arch_web.domain._base import WebContractRecord, require_text
from arch_web.domain.errors import WebContractReferenceError, WebContractValidationError
from arch_web.domain.references import ContractRef

_COLOR = re.compile(r"^#[0-9A-F]{6}$")
_TOKEN_NAME = re.compile(r"^[a-z][a-z0-9]*(?:\.[a-z0-9][a-z0-9]*)*$")


@unique
class PrimitiveTokenKind(StrEnum):
    COLOR = "color"
    FONT_FAMILY = "font_family"
    FONT_WEIGHT = "font_weight"
    FONT_SIZE = "font_size"
    SPACING = "spacing"
    RADIUS = "radius"
    BORDER_WIDTH = "border_width"
    ELEVATION = "elevation"
    OPACITY = "opacity"
    Z_LAYER = "z_layer"
    MOTION_DURATION = "motion_duration"
    MOTION_EASING = "motion_easing"
    BREAKPOINT = "breakpoint"


def _token_name(value: str, field_name: str) -> None:
    if not _TOKEN_NAME.fullmatch(value):
        raise WebContractValidationError(f"{field_name} must be a canonical dotted token name")


@dataclass(frozen=True, slots=True)
class PrimitiveToken(WebContractRecord):
    contract_type = "primitive_token"

    token_id: str
    kind: PrimitiveTokenKind
    value: str

    def __post_init__(self) -> None:
        _token_name(self.token_id, "token_id")
        require_text(self.value, "value")
        if self.kind is PrimitiveTokenKind.COLOR and not _COLOR.fullmatch(self.value):
            raise WebContractValidationError("Color primitives must use canonical #RRGGBB")


@dataclass(frozen=True, slots=True)
class PrimitiveTokenSet(WebContractRecord):
    contract_type = "primitive_token_set"

    token_set_id: str
    tokens: tuple[PrimitiveToken, ...]

    def __post_init__(self) -> None:
        require_text(self.token_set_id, "token_set_id")
        tokens = tuple(sorted(self.tokens, key=lambda item: item.token_id))
        ids = tuple(item.token_id for item in tokens)
        if len(ids) != len(set(ids)):
            raise WebContractValidationError("Primitive token IDs must be unique")
        object.__setattr__(self, "tokens", tokens)


@dataclass(frozen=True, slots=True)
class SemanticToken(WebContractRecord):
    contract_type = "semantic_token"

    role: str
    target_ref: str

    def __post_init__(self) -> None:
        _token_name(self.role, "role")
        _token_name(self.target_ref, "target_ref")


@dataclass(frozen=True, slots=True)
class SemanticTokenSet(WebContractRecord):
    contract_type = "semantic_token_set"

    token_set_id: str
    primitive_set_ref: ContractRef
    tokens: tuple[SemanticToken, ...]

    def __post_init__(self) -> None:
        require_text(self.token_set_id, "token_set_id")
        if self.primitive_set_ref.target_contract_type != PrimitiveTokenSet.contract_type:
            raise WebContractValidationError("primitive_set_ref has the wrong contract type")
        tokens = tuple(sorted(self.tokens, key=lambda item: item.role))
        roles = tuple(item.role for item in tokens)
        if len(roles) != len(set(roles)):
            raise WebContractValidationError("Semantic token roles must be unique")
        object.__setattr__(self, "tokens", tokens)

    def resolve(self, primitives: PrimitiveTokenSet) -> tuple[tuple[str, PrimitiveToken], ...]:
        self.primitive_set_ref.verify(primitives, primitives.token_set_id)
        primitive_by_id = {item.token_id: item for item in primitives.tokens}
        semantic_by_role = {item.role: item.target_ref for item in self.tokens}

        def visit(role: str, path: tuple[str, ...]) -> PrimitiveToken:
            if role in path:
                raise WebContractValidationError("Semantic token alias cycle detected")
            target = semantic_by_role.get(role)
            if target is None:
                raise WebContractReferenceError(f"Unresolved semantic token {role!r}")
            primitive = primitive_by_id.get(target)
            if primitive is not None:
                return primitive
            if target not in semantic_by_role:
                raise WebContractReferenceError(f"Unresolved token target {target!r}")
            return visit(target, (*path, role))

        return tuple((role, visit(role, ())) for role in sorted(semantic_by_role))


@dataclass(frozen=True, slots=True)
class ContrastPairSpec(WebContractRecord):
    contract_type = "contrast_pair_spec"

    pair_id: str
    foreground_role: str
    background_role: str
    minimum_ratio: float
    usage: str

    def __post_init__(self) -> None:
        require_text(self.pair_id, "pair_id")
        _token_name(self.foreground_role, "foreground_role")
        _token_name(self.background_role, "background_role")
        require_text(self.usage, "usage")
        if self.minimum_ratio < 1.0:
            raise WebContractValidationError("Contrast minimum ratio must be at least 1.0")


__all__ = (
    "ContrastPairSpec",
    "PrimitiveToken",
    "PrimitiveTokenKind",
    "PrimitiveTokenSet",
    "SemanticToken",
    "SemanticTokenSet",
)
