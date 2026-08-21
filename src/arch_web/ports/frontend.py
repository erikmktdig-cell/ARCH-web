"""Framework-neutral W06 executor and stack boundaries."""

from __future__ import annotations

from typing import Protocol

from arch_web.domain.frontend import (
    FrontendAssignmentPacket,
    FrontendEngineeringCheck,
    FrontendImplementationProposal,
)
from arch_web.domain.ui_specification import WebDesignSystemContract, WebUISpecificationContract
from arch_web.domain.workspace import ImplementationPlan, ResolvedStackManifest


class FrontendExecutorPort(Protocol):
    def propose(self, assignment: FrontendAssignmentPacket) -> FrontendImplementationProposal: ...


class FrontendStackAdapter(Protocol):
    @property
    def identity(self) -> str: ...

    def supports(self, stack: ResolvedStackManifest) -> bool: ...

    def compile_tokens(
        self, design: WebDesignSystemContract
    ) -> tuple[str, tuple[tuple[str, str, str], ...]]: ...

    def reference_proposal(
        self,
        assignment: FrontendAssignmentPacket,
        design: WebDesignSystemContract,
        ui: WebUISpecificationContract,
        plan: ImplementationPlan,
    ) -> FrontendImplementationProposal: ...

    def verify(
        self, proposal: FrontendImplementationProposal, source_tree_fingerprint: str
    ) -> tuple[FrontendEngineeringCheck, ...]: ...


__all__ = ("FrontendExecutorPort", "FrontendStackAdapter")
