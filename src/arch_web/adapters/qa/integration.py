"""Disposable local integration audit for an exact generated backend candidate."""

from __future__ import annotations

import hashlib
import runpy
import sqlite3
from collections.abc import Callable
from pathlib import Path
from typing import cast

from arch_web.application.architecture.planning import semantic_id
from arch_web.domain.qa import IntegrationQAEvidence, QACandidateBaseline, QARun, QAStatus


class LocalBackendIntegrationAdapter:
    """Executes generated service boundaries against a disposable application DB."""

    identity = "arch-web.local-backend-integration@0.1.0"

    def __init__(
        self,
        workspace_root: Path,
        service_path: str,
        schema_path: str,
        application_database_path: Path,
        runtime_database_path: Path,
    ) -> None:
        self._root = workspace_root.resolve()
        self._service = (self._root / service_path).resolve()
        self._schema = (self._root / schema_path).resolve()
        self._application_database = application_database_path.resolve()
        self._runtime_database = runtime_database_path.resolve()

    def audit(self, candidate: QACandidateBaseline, run: QARun) -> IntegrationQAEvidence:
        observations: list[str] = []
        passed = False
        try:
            if self._application_database == self._runtime_database:
                raise ValueError("application and Runtime databases must be separate")
            if self._root not in self._service.parents or self._root not in self._schema.parents:
                raise ValueError("integration artifact escapes the workspace")
            schema = self._schema.read_text(encoding="utf-8")
            namespace = runpy.run_path(str(self._service))
            create_item = cast(Callable[..., None], namespace["create_item"])
            get_item = cast(Callable[..., tuple[str, str, str]], namespace["get_item"])
            self._application_database.unlink(missing_ok=True)
            connection = sqlite3.connect(self._application_database)
            try:
                connection.executescript(schema)
                create_item(connection, "alice", "item-qa", "Selected")
                connection.commit()
                assert get_item(connection, "alice", "item-qa")[-1] == "Selected"
                observations.extend(("authorized_read:pass", "persistence:pass"))
                try:
                    get_item(connection, "bob", "item-qa")
                except PermissionError:
                    observations.append("cross_user_denied:pass")
                else:
                    raise AssertionError("cross-user read was not denied")
                try:
                    create_item(connection, "alice", "item-invalid", "")
                except ValueError:
                    observations.append("server_validation:pass")
                else:
                    raise AssertionError("invalid input was not denied")
            finally:
                connection.close()
            passed = not self._runtime_database.exists()
            observations.append(
                "runtime_database_separation:pass" if passed else "runtime_database_separation:fail"
            )
        except (AssertionError, KeyError, OSError, sqlite3.Error, ValueError) as error:
            observations.append(f"integration_failure:{type(error).__name__}")
        finally:
            self._application_database.unlink(missing_ok=True)
        digest = "sha256:" + hashlib.sha256("|".join(sorted(observations)).encode()).hexdigest()
        return IntegrationQAEvidence(
            semantic_id("QEV", {"category": "integration", "run": run, "digest": digest}),
            "frontend-backend-local-integration",
            candidate.canonical_fingerprint(),
            QAStatus.PASS if passed else QAStatus.FAIL,
            tuple(sorted({item.scenario_ref for item in run.results})),
            tuple(observations),
            (digest,),
        )


__all__ = ("LocalBackendIntegrationAdapter",)
