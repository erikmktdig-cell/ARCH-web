"""Framework-neutral stack selection contract."""

from __future__ import annotations

from dataclasses import dataclass

from arch_web.domain._base import WebContractRecord, freeze_strings, require_text
from arch_web.domain.enums import ArchitectureChoice

type StackValue = str | ArchitectureChoice


def _validate_choice(value: StackValue, field_name: str) -> None:
    if isinstance(value, str) and not isinstance(value, ArchitectureChoice):
        require_text(value, field_name)
        if value in {choice.value for choice in ArchitectureChoice}:
            raise ValueError(f"{field_name} must use ArchitectureChoice for {value!r}")


@dataclass(frozen=True, slots=True)
class WebStackProfile(WebContractRecord):
    contract_type = "web_stack_profile"

    contract_version: str
    profile_id: str
    language: StackValue
    frontend_framework: StackValue
    rendering_mode: StackValue
    package_manager: StackValue
    backend_model: StackValue
    database_provider: StackValue
    auth_provider: StackValue
    unit_test_runner: StackValue
    e2e_test_runner: StackValue
    deployment_target: StackValue
    runtime_requirement: StackValue
    constraints: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        from arch_web.contracts.versions import require_supported_version

        require_supported_version(self.contract_version)
        require_text(self.profile_id, "profile_id")
        for field_name in (
            "language",
            "frontend_framework",
            "rendering_mode",
            "package_manager",
            "backend_model",
            "database_provider",
            "auth_provider",
            "unit_test_runner",
            "e2e_test_runner",
            "deployment_target",
            "runtime_requirement",
        ):
            _validate_choice(getattr(self, field_name), field_name)
        object.__setattr__(
            self, "constraints", freeze_strings(self.constraints, "constraints", sort=True)
        )


__all__ = ("WebStackProfile",)
