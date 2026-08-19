"""Typed immutable references to contracts and evidence."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from arch_web.contracts.versions import CURRENT_WEB_CONTRACT_VERSION, require_supported_version
from arch_web.domain._base import WebContractRecord, require_text, validate_datetime
from arch_web.domain.errors import WebContractReferenceError


def _require_sha256(value: str | None, field_name: str, *, optional: bool = False) -> None:
    if value is None and optional:
        return
    if value is None or len(value) != 64 or any(char not in "0123456789abcdef" for char in value):
        raise WebContractReferenceError(f"{field_name} must be lowercase SHA-256 hex")


@dataclass(frozen=True, slots=True)
class ContractRef(WebContractRecord):
    contract_type = "contract_ref"

    target_contract_type: str
    contract_id: str
    contract_version: str
    fingerprint: str

    def __post_init__(self) -> None:
        require_text(self.target_contract_type, "target_contract_type")
        require_text(self.contract_id, "contract_id")
        require_supported_version(self.contract_version)
        _require_sha256(self.fingerprint, "fingerprint")

    def verify(self, target: WebContractRecord, target_id: str) -> None:
        version = getattr(target, "contract_version", CURRENT_WEB_CONTRACT_VERSION)
        if self.target_contract_type != target.contract_type:
            raise WebContractReferenceError("ContractRef target type mismatch")
        if self.contract_id != target_id:
            raise WebContractReferenceError("ContractRef target identity mismatch")
        if self.contract_version != version:
            raise WebContractReferenceError("ContractRef target version mismatch")
        if self.fingerprint != target.canonical_fingerprint():
            raise WebContractReferenceError("ContractRef target fingerprint mismatch")


@dataclass(frozen=True, slots=True)
class DesignReference(WebContractRecord):
    contract_type = "design_reference"

    design_ref_id: str
    kind: str
    uri: str
    content_fingerprint: str | None = None
    source_commit: str | None = None
    description: str | None = None
    captured_at: datetime | None = None

    def __post_init__(self) -> None:
        require_text(self.design_ref_id, "design_ref_id")
        require_text(self.kind, "kind")
        require_text(self.uri, "uri")
        _require_sha256(self.content_fingerprint, "content_fingerprint", optional=True)
        for field_name in ("source_commit", "description"):
            value = getattr(self, field_name)
            if value is not None:
                require_text(value, field_name)
        validate_datetime(self.captured_at, "captured_at")


@dataclass(frozen=True, slots=True)
class EvidenceRef(WebContractRecord):
    contract_type = "evidence_ref"

    evidence_id: str
    evidence_type: str
    uri: str
    content_fingerprint: str | None = None
    source_commit: str | None = None
    producer: str | None = None
    created_at: datetime | None = None

    def __post_init__(self) -> None:
        require_text(self.evidence_id, "evidence_id")
        require_text(self.evidence_type, "evidence_type")
        require_text(self.uri, "uri")
        _require_sha256(self.content_fingerprint, "content_fingerprint", optional=True)
        for field_name in ("source_commit", "producer"):
            value = getattr(self, field_name)
            if value is not None:
                require_text(value, field_name)
        validate_datetime(self.created_at, "created_at")


__all__ = ("ContractRef", "DesignReference", "EvidenceRef")
