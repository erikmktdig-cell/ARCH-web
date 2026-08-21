"""Explicit Python stdlib + SQLite reference backend adapter."""

from __future__ import annotations

import hashlib

from arch_web.application.architecture.planning import semantic_id
from arch_web.contracts.versions import CURRENT_WEB_CONTRACT_VERSION
from arch_web.domain.backend import (
    ApplicationDataContract,
    ApplicationMigrationPlan,
    AuthenticationContract,
    AuthorizationRule,
    BackendArtifact,
    BackendArtifactKind,
    BackendAssignmentPacket,
    BackendDataBinding,
    BackendEngineeringCheck,
    BackendImplementationProposal,
    BackendInterfaceContract,
    BindingClosureStatus,
    ExternalIntegrationContract,
    PersistenceContract,
)
from arch_web.domain.frontend import FrontendCheckStatus
from arch_web.domain.workspace import ImplementationPlan, ResolvedStackManifest


def _fingerprint(content: str) -> str:
    return "sha256:" + hashlib.sha256(content.encode()).hexdigest()


class PythonSQLiteBackendAdapter:
    """Small governance fixture selected only for an exact resolved stack."""

    identity = "arch-web.python-sqlite-reference@0.1.0"

    def supports(self, stack: ResolvedStackManifest) -> bool:
        return stack.language == "python@3.12" and stack.backend_model == "python-stdlib-sqlite@3"

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
    ) -> BackendImplementationProposal:
        if not assignment.selected_unit_refs:
            raise ValueError("Reference backend requires selected units")
        claims = {item.unit_ref: item for item in plan.path_claims}
        unit = assignment.selected_unit_refs[0]
        claim = claims[unit]
        root = claim.path_pattern.removesuffix("/**")
        source = '''"""Generated contract-bound service fixture."""

import sqlite3


def create_item(
    connection: sqlite3.Connection, actor_id: str, item_id: str, title: str
) -> None:
    if not actor_id or not item_id or not title:
        raise ValueError("validation")
    connection.execute(
        "INSERT INTO app_items (item_id, owner_id, title) VALUES (?, ?, ?)",
        (item_id, actor_id, title),
    )


def get_item(
    connection: sqlite3.Connection, actor_id: str, item_id: str
) -> tuple[str, str, str]:
    row = connection.execute(
        "SELECT item_id, owner_id, title FROM app_items "
        "WHERE item_id = ? AND owner_id = ?",
        (item_id, actor_id),
    ).fetchone()
    if row is None:
        raise PermissionError("unauthorized")
    return str(row[0]), str(row[1]), str(row[2])
'''
        migration = "\n".join(step.statement.rstrip() for step in migrations.steps) + "\n"
        artifacts = tuple(
            self._artifact(unit, claim.claim_id, f"{root}/{name}", kind, content)
            for name, kind, content in (
                ("service.py", BackendArtifactKind.SOURCE, source),
                ("schema.sql", BackendArtifactKind.MIGRATION, migration),
            )
        )
        operations = tuple(item.operation_id for item in interface.operations)
        bindings = tuple(
            BackendDataBinding(
                ref,
                operations[0] if operations else None,
                BindingClosureStatus.IMPLEMENTED if operations else BindingClosureStatus.BLOCKED,
            )
            for ref in assignment.pending_frontend_bindings
        )
        return BackendImplementationProposal(
            CURRENT_WEB_CONTRACT_VERSION,
            semantic_id(
                "BIP", {"assignment": assignment, "artifacts": artifacts, "bindings": bindings}
            ),
            assignment.canonical_fingerprint(),
            assignment.selected_unit_refs,
            artifacts,
            bindings,
            interface,
            data_contract,
            authentication,
            authorization_rules,
            persistence,
            migrations,
            integrations,
            (),
            (),
            self.identity,
            "0.1.0",
        )

    @staticmethod
    def _artifact(
        unit: str, claim: str, path: str, kind: BackendArtifactKind, content: str
    ) -> BackendArtifact:
        return BackendArtifact(
            semantic_id("BAR", {"unit": unit, "path": path, "content": content}),
            unit,
            claim,
            path,
            kind,
            content,
            _fingerprint(content),
        )

    def verify(
        self, proposal: BackendImplementationProposal, source_tree_fingerprint: str
    ) -> tuple[BackendEngineeringCheck, ...]:
        combined = "\n".join(item.content for item in proposal.artifacts)
        checks = {
            "format": all(item.content.endswith("\n") for item in proposal.artifacts),
            "lint": "eval(" not in combined and "shell=True" not in combined,
            "typecheck": "sqlite3.Connection" in combined,
            "unit": "validation" in combined,
            "repository": "VALUES (?, ?, ?)" in combined,
            "migration": "CREATE TABLE" in combined,
            "api_contract": bool(proposal.interface.operations),
            "authentication": bool(proposal.authentication.identity_source),
            "authorization": all(item.default_deny for item in proposal.authorization_rules),
            "integration": all(item.timeout_seconds > 0 for item in proposal.integrations),
            "build": bool(proposal.artifacts),
            "security": "https://" not in combined and "arch_runtime" not in combined,
        }
        return tuple(
            BackendEngineeringCheck(
                semantic_id("BCK", {"kind": kind, "tree": source_tree_fingerprint}),
                kind,
                self.identity,
                "built-in@0.1.0",
                source_tree_fingerprint,
                FrontendCheckStatus.PASS if passed else FrontendCheckStatus.FAIL,
                0 if passed else 1,
                _fingerprint(f"{kind}:{passed}"),
                ("sanitized-offline-analysis",),
            )
            for kind, passed in sorted(checks.items())
        )


__all__ = ("PythonSQLiteBackendAdapter",)
