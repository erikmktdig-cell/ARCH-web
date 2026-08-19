"""Public pure contract serialization boundary."""

from arch_web.contracts.canonical import canonical_bytes, contract_fingerprint
from arch_web.contracts.codec import decode_contract, encode_contract
from arch_web.contracts.versions import (
    CURRENT_WEB_CONTRACT_VERSION,
    SUPPORTED_WEB_CONTRACT_VERSIONS,
)

__all__ = (
    "CURRENT_WEB_CONTRACT_VERSION",
    "SUPPORTED_WEB_CONTRACT_VERSIONS",
    "canonical_bytes",
    "contract_fingerprint",
    "decode_contract",
    "encode_contract",
)
