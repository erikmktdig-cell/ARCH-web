"""Explicit fail-closed codecs for approved ARCH Web records."""

from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import datetime
from typing import Any, cast

from arch_web.contracts.canonical import canonical_bytes
from arch_web.domain._base import WebContractRecord
from arch_web.domain.enums import (
    ArchitectureChoice,
    ProjectKind,
    RequirementCategory,
    RequirementPriority,
    RequirementStatus,
    RouteVisibility,
    SurfaceType,
    WebLifecycleStatus,
    WebRoute,
)
from arch_web.domain.errors import WebContractIntegrityError, WebContractValidationError
from arch_web.domain.information_architecture import WebInformationArchitectureContract
from arch_web.domain.product_brief import WebProductBrief
from arch_web.domain.project import WebProjectProfile
from arch_web.domain.references import ContractRef, DesignReference, EvidenceRef
from arch_web.domain.requirements import WebRequirement, WebRequirementsContract
from arch_web.domain.requirements_review import (
    FindingCode,
    FindingSeverity,
    RequirementFinding,
    RequirementsReadiness,
    RequirementsReviewPackage,
    RouteRecommendation,
)
from arch_web.domain.stack import WebStackProfile
from arch_web.domain.surfaces import WebRouteContract, WebSurface


def encode_contract(value: WebContractRecord) -> bytes:
    return canonical_bytes(value)


def decode_contract[ContractT: WebContractRecord](
    contract_class: type[ContractT], payload: bytes, *, expected_fingerprint: str | None = None
) -> ContractT:
    try:
        raw = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise WebContractValidationError("Payload is not valid UTF-8 JSON") from error
    if not isinstance(raw, dict):
        raise WebContractValidationError("Contract payload must be a JSON object")
    result = decode_contract_data(contract_class, raw)
    canonical = encode_contract(result)
    if payload != canonical:
        raise WebContractIntegrityError("Payload is valid JSON but is not canonical")
    if expected_fingerprint is not None and result.canonical_fingerprint() != expected_fingerprint:
        raise WebContractIntegrityError("Contract fingerprint mismatch")
    return result


def _choice(value: str) -> str | ArchitectureChoice:
    return (
        ArchitectureChoice(value) if value in {item.value for item in ArchitectureChoice} else value
    )


def _contract_ref(value: Mapping[str, Any] | None) -> ContractRef | None:
    return None if value is None else ContractRef(**value)


def _evidence_ref(value: Mapping[str, Any] | None) -> EvidenceRef | None:
    if value is None:
        return None
    data = dict(value)
    data["created_at"] = _datetime(data.get("created_at"))
    return EvidenceRef(**data)


def _datetime(value: str | None) -> datetime | None:
    return None if value is None else datetime.fromisoformat(value.replace("Z", "+00:00"))


def decode_contract_data[ContractT: WebContractRecord](
    contract_class: type[ContractT], value: Mapping[str, Any]
) -> ContractT:
    data = dict(value)
    try:
        if contract_class is ContractRef:
            result: WebContractRecord = ContractRef(**data)
        elif contract_class is DesignReference:
            data["captured_at"] = _datetime(data.get("captured_at"))
            result = DesignReference(**data)
        elif contract_class is EvidenceRef:
            data["created_at"] = _datetime(data.get("created_at"))
            result = EvidenceRef(**data)
        elif contract_class is WebStackProfile:
            choice_fields = set(data) - {"contract_version", "profile_id", "constraints"}
            for field_name in choice_fields:
                data[field_name] = _choice(data[field_name])
            result = WebStackProfile(**data)
        elif contract_class is WebRequirement:
            data["category"] = RequirementCategory(data["category"])
            data["priority"] = RequirementPriority(data["priority"])
            data["route_requirement"] = WebRoute(data["route_requirement"])
            data["status"] = RequirementStatus(data["status"])
            result = WebRequirement(**data)
        elif contract_class is WebRequirementsContract:
            data["route"] = WebRoute(data["route"])
            data["requirements"] = tuple(
                WebRequirement.from_data(item) for item in data["requirements"]
            )
            data["approval_evidence_ref"] = _evidence_ref(data.get("approval_evidence_ref"))
            result = WebRequirementsContract(**data)
        elif contract_class is WebSurface:
            data["surface_type"] = SurfaceType(data["surface_type"])
            result = WebSurface(**data)
        elif contract_class is WebRouteContract:
            data["visibility"] = RouteVisibility(data["visibility"])
            result = WebRouteContract(**data)
        elif contract_class is WebInformationArchitectureContract:
            data["surfaces"] = tuple(WebSurface.from_data(item) for item in data["surfaces"])
            data["routes"] = tuple(WebRouteContract.from_data(item) for item in data["routes"])
            result = WebInformationArchitectureContract(**data)
        elif contract_class is WebProjectProfile:
            data["route"] = WebRoute(data["route"])
            data["project_kind"] = ProjectKind(data["project_kind"])
            data["status"] = WebLifecycleStatus(data["status"])
            data["stack_profile_ref"] = cast(ContractRef, _contract_ref(data["stack_profile_ref"]))
            data["requirements_ref"] = _contract_ref(data.get("requirements_ref"))
            data["information_architecture_ref"] = _contract_ref(
                data.get("information_architecture_ref")
            )
            data["design_system_ref"] = _contract_ref(data.get("design_system_ref"))
            data["created_at"] = _datetime(data.get("created_at"))
            result = WebProjectProfile(**data)
        elif contract_class is WebProductBrief:
            data["project_kind_hypothesis"] = ProjectKind(data["project_kind_hypothesis"])
            data["route"] = WebRoute(data["route"])
            data["source_refs"] = tuple(
                cast(EvidenceRef, _evidence_ref(item)) for item in data["source_refs"]
            )
            data["approval_evidence_ref"] = _evidence_ref(data.get("approval_evidence_ref"))
            result = WebProductBrief(**data)
        elif contract_class is RequirementFinding:
            data["code"] = FindingCode(data["code"])
            data["severity"] = FindingSeverity(data["severity"])
            result = RequirementFinding(**data)
        elif contract_class is RouteRecommendation:
            data["recommended_route"] = WebRoute(data["recommended_route"])
            result = RouteRecommendation(**data)
        elif contract_class is RequirementsReviewPackage:
            data["product_brief_ref"] = cast(ContractRef, _contract_ref(data["product_brief_ref"]))
            data["requirements_contract_ref"] = cast(
                ContractRef, _contract_ref(data["requirements_contract_ref"])
            )
            data["gap_findings"] = tuple(
                RequirementFinding.from_data(item) for item in data["gap_findings"]
            )
            data["conflict_findings"] = tuple(
                RequirementFinding.from_data(item) for item in data["conflict_findings"]
            )
            data["route_recommendation"] = RouteRecommendation.from_data(
                data["route_recommendation"]
            )
            data["readiness"] = RequirementsReadiness(data["readiness"])
            data["source_evidence_refs"] = tuple(
                cast(EvidenceRef, _evidence_ref(item)) for item in data["source_evidence_refs"]
            )
            data["created_at"] = _datetime(data.get("created_at"))
            result = RequirementsReviewPackage(**data)
        else:
            raise WebContractValidationError(f"No approved decoder for {contract_class!r}")
        return cast(ContractT, result)
    except (KeyError, TypeError, ValueError) as error:
        if isinstance(error, WebContractValidationError):
            raise
        raise WebContractValidationError(
            "Contract payload does not match its approved schema"
        ) from error


__all__ = ("decode_contract", "encode_contract")
