"""Immutable product intent captured before architecture decisions."""

from __future__ import annotations

from dataclasses import dataclass

from arch_web.contracts.versions import require_supported_version
from arch_web.domain._base import WebContractRecord, freeze_strings, require_text
from arch_web.domain.enums import ProjectKind, WebRoute
from arch_web.domain.errors import WebContractValidationError
from arch_web.domain.references import EvidenceRef


def _optional_normalized(value: str, field_name: str) -> None:
    if value != " ".join(value.split()):
        raise WebContractValidationError(f"{field_name} must already be whitespace-normalized")


@dataclass(frozen=True, slots=True)
class WebProductBrief(WebContractRecord):
    """Framework-neutral, reviewable product intent."""

    contract_type = "web_product_brief"

    contract_version: str
    brief_id: str
    project_id: str
    name: str
    problem_statement: str
    primary_goal: str
    target_users: tuple[str, ...]
    value_proposition: str
    project_kind_hypothesis: ProjectKind
    delivery_mode: str
    core_capabilities: tuple[str, ...]
    content_needs: tuple[str, ...]
    data_needs: tuple[str, ...]
    integrations: tuple[str, ...]
    auth_security_needs: tuple[str, ...]
    responsive_expectations: tuple[str, ...]
    accessibility_expectations: tuple[str, ...]
    performance_expectations: tuple[str, ...]
    operational_expectations: tuple[str, ...]
    constraints: tuple[str, ...]
    assumptions: tuple[str, ...]
    exclusions: tuple[str, ...]
    unresolved_questions: tuple[str, ...]
    source_refs: tuple[EvidenceRef, ...]
    route: WebRoute
    approval_evidence_ref: EvidenceRef | None = None

    def __post_init__(self) -> None:
        require_supported_version(self.contract_version)
        for field_name in ("brief_id", "project_id", "name", "delivery_mode"):
            require_text(getattr(self, field_name), field_name)
        for field_name in ("problem_statement", "primary_goal", "value_proposition"):
            _optional_normalized(getattr(self, field_name), field_name)
        collection_fields = (
            "target_users",
            "core_capabilities",
            "content_needs",
            "data_needs",
            "integrations",
            "auth_security_needs",
            "responsive_expectations",
            "accessibility_expectations",
            "performance_expectations",
            "operational_expectations",
            "constraints",
            "assumptions",
            "exclusions",
            "unresolved_questions",
        )
        for field_name in collection_fields:
            object.__setattr__(
                self,
                field_name,
                freeze_strings(getattr(self, field_name), field_name, sort=True),
            )
        refs = tuple(sorted(self.source_refs, key=lambda item: item.evidence_id))
        if len({item.evidence_id for item in refs}) != len(refs):
            raise WebContractValidationError("source_refs contains duplicate evidence IDs")
        object.__setattr__(self, "source_refs", refs)


__all__ = ("WebProductBrief",)
