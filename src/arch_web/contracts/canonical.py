"""Single deterministic JSON policy for ARCH web contracts."""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping
from dataclasses import fields, is_dataclass
from datetime import UTC, datetime
from enum import Enum
from typing import TYPE_CHECKING, cast

from arch_web.domain.errors import WebContractValidationError

if TYPE_CHECKING:
    from arch_web.domain._base import WebContractRecord

type JsonScalar = str | int | float | bool | None
type JsonValue = JsonScalar | list[JsonValue] | dict[str, JsonValue]


def to_canonical_data(value: object) -> JsonValue:
    if value is None or isinstance(value, (str, int, bool)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise WebContractValidationError("Canonical JSON rejects NaN and Infinity")
        return value
    if isinstance(value, Enum):
        return cast(str, value.value)
    if isinstance(value, datetime):
        if value.tzinfo is None or value.utcoffset() is None:
            raise WebContractValidationError("Canonical JSON rejects naive datetimes")
        return value.astimezone(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")
    if is_dataclass(value) and not isinstance(value, type):
        return {
            field.name: to_canonical_data(getattr(value, field.name))
            for field in fields(value)
            if field.init
        }
    if isinstance(value, Mapping):
        if not all(isinstance(key, str) for key in value):
            raise WebContractValidationError("Canonical JSON object keys must be strings")
        return {key: to_canonical_data(value[key]) for key in sorted(value)}
    if isinstance(value, (tuple, list)):
        return [to_canonical_data(item) for item in value]
    raise WebContractValidationError(f"Unsupported canonical value: {type(value).__name__}")


def canonical_bytes(value: object) -> bytes:
    return json.dumps(
        to_canonical_data(value),
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def contract_fingerprint(value: WebContractRecord) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


__all__ = ("JsonValue", "canonical_bytes", "contract_fingerprint")
