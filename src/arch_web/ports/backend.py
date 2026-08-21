"""Framework-neutral W07 executor and stack boundaries."""

from __future__ import annotations

from typing import Protocol

from arch_web.domain.backend import (
    ApplicationDataContract,
    ApplicationMigrationPlan,
    AuthenticationContract,
    AuthorizationRule,
    BackendAssignmentPacket,
    BackendEngineeringCheck,
    BackendImplementationProposal,
    BackendInterfaceContract,
    ExternalIntegrationContract,
    PersistenceContract,
)
from arch_web.domain.workspace import ImplementationPlan, ResolvedStackManifest


class BackendExecutorPort(Protocol):
    def propose(self, assignment: BackendAssignmentPacket) -> BackendImplementationProposal: ...


class BackendStackAdapter(Protocol):
    @property
    def identity(self) -> str: ...

    def supports(self, stack: ResolvedStackManifest) -> bool: ...

    def reference_proposal(
        self,
        assignment: BackendAssignmentPacket,
        interface: BackendInterfaceContract,
        data_contract: ApplicationDataContract,
        authentication: AuthenticationContract,
        authorization_rules: tuple[AuthorizationRule, ...],
        persistence: PersistenceContract,
        migrations: ApplicationMigrationPlan,
        integrations: tuple[ExternalIntegrationContract, ...],
        plan: ImplementationPlan,
    ) -> BackendImplementationProposal: ...

    def verify(
        self, proposal: BackendImplementationProposal, source_tree_fingerprint: str
    ) -> tuple[BackendEngineeringCheck, ...]: ...


__all__ = ("BackendExecutorPort", "BackendStackAdapter")
