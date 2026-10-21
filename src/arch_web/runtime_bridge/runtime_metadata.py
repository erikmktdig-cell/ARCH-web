"""Deterministic string-only metadata for public Runtime commands."""

from __future__ import annotations

from collections.abc import Mapping

from arch_web.contracts.canonical import JsonValue, canonical_bytes
from arch_web.domain.errors import WebContractValidationError


def metadata_string(value: str) -> str:
    """Return one already-normalized scalar metadata value."""

    if not isinstance(value, str):
        raise WebContractValidationError("Runtime metadata string must be a string")
    if not value or value.strip() != value:
        raise WebContractValidationError("Runtime metadata string must be normalized")
    return value


def metadata_integer(value: int) -> str:
    """Encode an integer as canonical decimal text."""

    if isinstance(value, bool) or not isinstance(value, int):
        raise WebContractValidationError("Runtime metadata integer must be an integer")
    return str(value)


def metadata_canonical_json(value: JsonValue) -> str:
    """Encode structured metadata as compact deterministic canonical JSON."""

    return canonical_bytes(value).decode("utf-8")


def build_runtime_metadata(
    *,
    strings: Mapping[str, str | None],
    integers: Mapping[str, int] | None = None,
    structured: Mapping[str, JsonValue] | None = None,
) -> dict[str, str]:
    """Build a sorted string-only mapping; absent optional strings are omitted."""

    result: dict[str, str] = {}
    for key, string_value in strings.items():
        normalized_key = metadata_string(key)
        if string_value is not None:
            result[normalized_key] = metadata_string(string_value)
    for key, integer_value in (integers or {}).items():
        normalized_key = metadata_string(key)
        if normalized_key in result:
            raise WebContractValidationError(f"Duplicate Runtime metadata key: {normalized_key}")
        result[normalized_key] = metadata_integer(integer_value)
    for key, structured_value in (structured or {}).items():
        normalized_key = metadata_string(key)
        if normalized_key in result:
            raise WebContractValidationError(f"Duplicate Runtime metadata key: {normalized_key}")
        result[normalized_key] = metadata_canonical_json(structured_value)
    return dict(sorted(result.items()))


__all__ = (
    "build_runtime_metadata",
    "metadata_canonical_json",
    "metadata_integer",
    "metadata_string",
)
