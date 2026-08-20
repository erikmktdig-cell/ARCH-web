"""Public pure contract serialization boundary."""

from __future__ import annotations

from typing import TYPE_CHECKING

from arch_web.contracts.canonical import canonical_bytes, contract_fingerprint
from arch_web.contracts.versions import (
    CURRENT_WEB_CONTRACT_VERSION,
    SUPPORTED_WEB_CONTRACT_VERSIONS,
)

if TYPE_CHECKING:
    from arch_web.domain._base import WebContractRecord


def encode_contract(value: WebContractRecord) -> bytes:
    from arch_web.contracts.codec import encode_contract as encode

    return encode(value)


def decode_contract[ContractT: WebContractRecord](
    contract_class: type[ContractT], payload: bytes, *, expected_fingerprint: str | None = None
) -> ContractT:
    from arch_web.contracts.codec import decode_contract as decode

    return decode(contract_class, payload, expected_fingerprint=expected_fingerprint)


__all__ = (
    "CURRENT_WEB_CONTRACT_VERSION",
    "SUPPORTED_WEB_CONTRACT_VERSIONS",
    "canonical_bytes",
    "contract_fingerprint",
    "decode_contract",
    "encode_contract",
)
