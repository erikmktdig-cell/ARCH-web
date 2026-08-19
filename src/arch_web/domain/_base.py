"""Internal immutable-record validation helpers."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Any, ClassVar, Self

from arch_web.contracts.versions import require_supported_version
from arch_web.domain.errors import WebContractValidationError

if TYPE_CHECKING:
    from arch_web.contracts.canonical import JsonValue


def require_text(value: str, field_name: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise WebContractValidationError(f"{field_name} must not be empty")
    if normalized != value:
        raise WebContractValidationError(f"{field_name} must already be normalized")
    return normalized


def freeze_strings(
    values: Iterable[str], field_name: str, *, sort: bool = False
) -> tuple[str, ...]:
    frozen = tuple(require_text(value, field_name) for value in values)
    if len(frozen) != len(set(frozen)):
        raise WebContractValidationError(f"{field_name} contains duplicates")
    return tuple(sorted(frozen)) if sort else frozen


def freeze_string_map(
    value: Mapping[str, str] | Iterable[tuple[str, str]], field_name: str
) -> tuple[tuple[str, str], ...]:
    items = tuple(value.items()) if isinstance(value, Mapping) else tuple(value)
    normalized = tuple(
        (require_text(key, f"{field_name} key"), require_text(item, f"{field_name}[{key}]"))
        for key, item in items
    )
    keys = tuple(key for key, _ in normalized)
    if len(keys) != len(set(keys)):
        raise WebContractValidationError(f"{field_name} contains duplicate keys")
    return tuple(sorted(normalized))


def validate_datetime(value: datetime | None, field_name: str) -> None:
    if value is not None and (value.tzinfo is None or value.utcoffset() is None):
        raise WebContractValidationError(f"{field_name} must be timezone-aware")


@dataclass(frozen=True, slots=True)
class WebContractRecord:
    """Behavior shared by immutable canonical records."""

    contract_type: ClassVar[str]

    def canonical_data(self) -> JsonValue:
        from arch_web.contracts.canonical import to_canonical_data

        return to_canonical_data(self)

    def canonical_bytes(self) -> bytes:
        from arch_web.contracts.canonical import canonical_bytes

        return canonical_bytes(self)

    def canonical_fingerprint(self) -> str:
        from arch_web.contracts.canonical import contract_fingerprint

        return contract_fingerprint(self)

    @classmethod
    def from_data(cls, value: Mapping[str, Any]) -> Self:
        from arch_web.contracts.codec import decode_contract_data

        decoded = decode_contract_data(cls, value)
        if not isinstance(decoded, cls):
            raise TypeError(f"Decoder returned {type(decoded)!r}, expected {cls!r}")
        return decoded


def validate_versioned_identity(contract_version: str, identifier: str, field_name: str) -> None:
    require_supported_version(contract_version)
    require_text(identifier, field_name)
