"""Immutable W07 commands and results."""

from __future__ import annotations

from dataclasses import dataclass

from arch_web.application.workspace.models import PrepareWorkspaceResult
from arch_web.domain._base import WebContractRecord, freeze_strings, require_text
from arch_web.domain.backend import (
    ApplicationDataContract,
    ApplicationMigrationPlan,
    AuthenticationContract,
    AuthorizationRule,
    BackendAssignmentPacket,
    BackendCompletionPackage,
    BackendImplementationProposal,
    BackendInterfaceContract,
    ExternalIntegrationContract,
    PersistenceContract,
)
from arch_web.domain.enums import WebLifecycleStatus
from arch_web.domain.frontend import FrontendCompletionPackage, FrontendImplementationProposal
from arch_web.domain.information_architecture import WebInformationArchitectureContract
from arch_web.domain.workspace import (
    WorkspaceBaseline,
    WorkspaceExecutionPolicy,
    WorkspaceExecutionReceipt,
    WorkspaceTarget,
)


@dataclass(frozen=True, slots=True)
class PrepareBackendCommand(WebContractRecord):
    contract_type = "prepare_backend_command"
    project_id: str
    project_status: WebLifecycleStatus
    runtime_record_version: int
    runtime_record_fingerprint: str
    requirements_fingerprint: str
    architecture: WebInformationArchitectureContract
    prepared_workspace: PrepareWorkspaceResult
    frontend_completion: FrontendCompletionPackage
    frontend_proposal: FrontendImplementationProposal
    current_baseline: WorkspaceBaseline
    selected_unit_refs: tuple[str, ...]
    interface: BackendInterfaceContract | None
    data_contract: ApplicationDataContract | None
    authentication: AuthenticationContract | None
    authorization_rules: tuple[AuthorizationRule, ...]
    persistence: PersistenceContract | None
    migrations: ApplicationMigrationPlan | None
    integrations: tuple[ExternalIntegrationContract, ...]

    def __post_init__(self) -> None:
        for name in ("project_id", "runtime_record_fingerprint", "requirements_fingerprint"):
            require_text(getattr(self, name), name)
        if self.runtime_record_version < 1:
            raise ValueError("runtime_record_version must be positive")
        object.__setattr__(
            self,
            "selected_unit_refs",
            freeze_strings(self.selected_unit_refs, "selected_unit_refs", sort=True),
        )
        object.__setattr__(
            self,
            "authorization_rules",
            tuple(sorted(self.authorization_rules, key=lambda item: item.rule_id)),
        )
        object.__setattr__(
            self,
            "integrations",
            tuple(sorted(self.integrations, key=lambda item: item.integration_id)),
        )


@dataclass(frozen=True, slots=True)
class PrepareBackendResult(WebContractRecord):
    contract_type = "prepare_backend_result"
    assignment: BackendAssignmentPacket
    execution_workspace: PrepareWorkspaceResult
    not_applicable_completion: BackendCompletionPackage | None


@dataclass(frozen=True, slots=True)
class ApplyBackendUnitCommand:
    execution_id: str
    project_status: WebLifecycleStatus
    assignment: BackendAssignmentPacket
    proposal: BackendImplementationProposal
    prepared_workspace: PrepareWorkspaceResult
    target: WorkspaceTarget
    policy: WorkspaceExecutionPolicy

    def __post_init__(self) -> None:
        require_text(self.execution_id, "execution_id")


@dataclass(frozen=True, slots=True)
class ApplyBackendUnitResult:
    proposal: BackendImplementationProposal
    receipt: WorkspaceExecutionReceipt


@dataclass(frozen=True, slots=True)
class VerifyBackendCommand:
    project_status: WebLifecycleStatus
    assignment: BackendAssignmentPacket
    applied: ApplyBackendUnitResult
    prepared_workspace: PrepareWorkspaceResult
    frontend_completion: FrontendCompletionPackage
    required_check_kinds: tuple[str, ...]

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "required_check_kinds",
            freeze_strings(self.required_check_kinds, "required_check_kinds", sort=True),
        )


@dataclass(frozen=True, slots=True)
class VerifyBackendResult(WebContractRecord):
    contract_type = "verify_backend_result"
    completion: BackendCompletionPackage


__all__ = tuple(name for name in globals() if name.endswith(("Command", "Result")))
