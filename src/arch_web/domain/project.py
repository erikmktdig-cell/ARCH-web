"""Top-level web project profile."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from arch_web.contracts.versions import require_supported_version
from arch_web.domain._base import WebContractRecord, freeze_strings, require_text, validate_datetime
from arch_web.domain.enums import ProjectKind, WebLifecycleStatus, WebRoute
from arch_web.domain.errors import WebContractReferenceError
from arch_web.domain.references import ContractRef, DesignReference


@dataclass(frozen=True, slots=True)
class WebProjectProfile(WebContractRecord):
    contract_type = "web_project_profile"

    contract_version: str
    project_id: str
    name: str
    route: WebRoute
    project_kind: ProjectKind
    primary_goal: str
    target_users: tuple[str, ...]
    delivery_mode: str
    locale: str
    status: WebLifecycleStatus
    stack_profile_ref: ContractRef
    requirements_ref: ContractRef | None = None
    information_architecture_ref: ContractRef | None = None
    design_system_ref: ContractRef | None = None
    created_at: datetime | None = None

    def __post_init__(self) -> None:
        require_supported_version(self.contract_version)
        for field_name in ("project_id", "name", "primary_goal", "delivery_mode", "locale"):
            require_text(getattr(self, field_name), field_name)
        object.__setattr__(
            self, "target_users", freeze_strings(self.target_users, "target_users", sort=True)
        )
        validate_datetime(self.created_at, "created_at")
        expected_types = {
            "stack_profile_ref": "web_stack_profile",
            "requirements_ref": "web_requirements_contract",
            "information_architecture_ref": "web_information_architecture_contract",
            "design_system_ref": "design_reference",
        }
        for field_name, expected_type in expected_types.items():
            reference = getattr(self, field_name)
            if reference is not None and reference.target_contract_type != expected_type:
                raise WebContractReferenceError(
                    f"{field_name} must target {expected_type!r}, "
                    f"got {reference.target_contract_type!r}"
                )

    def verify_stack(self, target: WebContractRecord) -> None:
        self.stack_profile_ref.verify(target, getattr(target, "profile_id", ""))

    def verify_requirements(self, target: WebContractRecord) -> None:
        if self.requirements_ref is None:
            raise WebContractReferenceError("Project has no requirements reference")
        if getattr(target, "project_id", None) != self.project_id:
            raise WebContractReferenceError("Requirements belong to a different project")
        self.requirements_ref.verify(target, getattr(target, "contract_id", ""))

    def verify_information_architecture(self, target: WebContractRecord) -> None:
        if self.information_architecture_ref is None:
            raise WebContractReferenceError("Project has no information architecture reference")
        if getattr(target, "project_id", None) != self.project_id:
            raise WebContractReferenceError(
                "Information architecture belongs to a different project"
            )
        self.information_architecture_ref.verify(target, getattr(target, "contract_id", ""))

    def verify_design(self, target: DesignReference) -> None:
        if self.design_system_ref is None:
            raise WebContractReferenceError("Project has no design reference")
        self.design_system_ref.verify(target, target.design_ref_id)


__all__ = ("WebProjectProfile",)
