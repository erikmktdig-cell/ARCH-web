"""Explicit disposable loopback deployment provider for W09 evidence."""

from __future__ import annotations

import functools
import hashlib
import http.server
import json
import shutil
import threading
import urllib.request
from pathlib import Path

from arch_web.application.architecture.planning import semantic_id
from arch_web.application.release.errors import DeploymentExecutionError
from arch_web.domain.release import (
    DeploymentExecutionAuthorization,
    DeploymentOutcome,
    DeploymentPlan,
    DeploymentReceipt,
    PostDeployVerificationEvidence,
    PostDeployVerificationPlan,
    ProductionMigrationExecutionEvidence,
    ProductionMigrationPlan,
    ReleaseArtifact,
    RollbackExecutionEvidence,
    RollbackPlan,
    TargetEnvironment,
)
from arch_web.domain.workspace import ReconciliationStatus


class _QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, _format: str, *_args: object) -> None:
        return


class LocalDeploymentProvider:
    """Copies one immutable artifact and serves it on loopback for governed verification."""

    identity = "arch-web.local-deployment@0.1.0"

    def __init__(self, deployment_root: Path, migration_state_path: Path | None = None) -> None:
        self._root = deployment_root.resolve()
        self._root.mkdir(parents=True, exist_ok=True)
        self._migration_state_path = (
            None if migration_state_path is None else migration_state_path.resolve()
        )
        self._executions: dict[str, tuple[str, DeploymentReceipt]] = {}
        self._servers: dict[str, tuple[http.server.ThreadingHTTPServer, threading.Thread]] = {}

    def discover_capabilities(self) -> tuple[str, ...]:
        return ("artifact_promotion", "direct_replace", "health_observation", "rollback")

    @staticmethod
    def _file_digest(path: Path) -> str:
        return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()

    def deploy(
        self,
        authorization: DeploymentExecutionAuthorization,
        plan: DeploymentPlan,
        artifact: ReleaseArtifact,
        target: TargetEnvironment,
        migration_plan: ProductionMigrationPlan | None,
    ) -> DeploymentReceipt:
        request_fingerprint = hashlib.sha256(
            f"{authorization.canonical_fingerprint()}:{plan.canonical_fingerprint()}".encode()
        ).hexdigest()
        prior = self._executions.get(authorization.execution_id)
        if prior is not None:
            if prior[0] != request_fingerprint:
                raise DeploymentExecutionError("Deployment execution ID conflict")
            return prior[1]
        source = Path(artifact.uri).resolve()
        if not source.is_file() or self._file_digest(source) != artifact.digest:
            raise DeploymentExecutionError("Artifact digest mismatch")
        if migration_plan is not None and self._migration_state_path is not None:
            before = self._migration_state_path.read_text(encoding="utf-8").strip()
            if before != migration_plan.expected_schema_version:
                raise DeploymentExecutionError("Application migration schema precondition failed")
            self._migration_state_path.write_text(
                migration_plan.postcondition_schema_version, encoding="utf-8"
            )
        provider_id = semantic_id(
            "LDP", {"execution": authorization.execution_id, "digest": artifact.digest}
        )
        deploy_dir = self._root / provider_id
        deploy_dir.mkdir(parents=True, exist_ok=False)
        deployed = deploy_dir / "index.html"
        shutil.copyfile(source, deployed)
        observed = self._file_digest(deployed)
        metadata = deploy_dir / "deployment.json"
        metadata.write_text(
            json.dumps(
                {"artifact_digest": observed, "environment": target.environment_id}, sort_keys=True
            ),
            encoding="utf-8",
        )
        handler = functools.partial(_QuietHandler, directory=str(deploy_dir))
        server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
        thread = threading.Thread(
            target=server.serve_forever, name="arch-web-deployment", daemon=True
        )
        thread.start()
        endpoint = f"http://127.0.0.1:{server.server_port}/"
        migration_evidence = None
        if migration_plan is not None:
            migration_evidence = ProductionMigrationExecutionEvidence(
                migration_plan.canonical_fingerprint(),
                migration_plan.target_datastore,
                migration_plan.expected_schema_version,
                migration_plan.postcondition_schema_version,
                migration_plan.migration_ids,
                True,
                "sha256:" + hashlib.sha256(migration_plan.canonical_bytes()).hexdigest(),
            )
        receipt = DeploymentReceipt(
            authorization.execution_id,
            authorization.candidate_fingerprint,
            plan.canonical_fingerprint(),
            authorization.provider_profile_id,
            target.environment_id,
            artifact.digest,
            provider_id,
            authorization.expected_prior_deployment_ref,
            endpoint,
            observed,
            DeploymentOutcome.APPLIED_PENDING_VERIFICATION,
            ReconciliationStatus.CLEAN,
            self.identity,
            ("sha256:" + hashlib.sha256(metadata.read_bytes()).hexdigest(),),
            migration_evidence,
        )
        self._servers[provider_id] = (server, thread)
        self._executions[authorization.execution_id] = (request_fingerprint, receipt)
        return receipt

    def verify(
        self,
        plan: PostDeployVerificationPlan,
        receipt: DeploymentReceipt,
        target: TargetEnvironment,
    ) -> PostDeployVerificationEvidence:
        reachable = health = smoke = backend = security = True
        body = b""
        try:
            assert receipt.endpoint is not None
            with urllib.request.urlopen(receipt.endpoint, timeout=5) as response:
                body = response.read(1_000_000)
                reachable = health = response.status == 200
        except (AssertionError, OSError):
            reachable = health = False
        lowered = body.lower()
        smoke = b"<main" in lowered and b"data-release-digest" in lowered
        backend = b'data-backend-health="pass"' in lowered
        security = b'data-security-smoke="pass"' in lowered
        leakage = any(marker in lowered for marker in (b"mock-api", b"localhost:3000", b"test.db"))
        tls = not target.tls_required or (receipt.endpoint or "").startswith("https://")
        observed = receipt.observed_artifact_digest or "sha256:" + "0" * 64
        passed = all(
            (
                reachable,
                health,
                smoke,
                backend,
                security,
                tls,
                not leakage,
                observed == plan.expected_artifact_digest,
            )
        )
        checks = (
            ("artifact", "pass" if observed == plan.expected_artifact_digest else "fail"),
            ("backend", "pass" if backend else "fail"),
            ("health", "pass" if health else "fail"),
            ("mock_leakage", "fail" if leakage else "pass"),
            ("security", "pass" if security else "fail"),
            ("smoke", "pass" if smoke else "fail"),
            ("tls", "pass" if tls else "fail"),
        )
        return PostDeployVerificationEvidence(
            semantic_id("PVE", {"plan": plan, "checks": checks}),
            plan.canonical_fingerprint(),
            receipt.canonical_fingerprint(),
            observed,
            checks,
            reachable,
            health,
            smoke,
            backend,
            security,
            tls,
            leakage,
            passed,
        )

    def rollback(self, plan: RollbackPlan, receipt: DeploymentReceipt) -> RollbackExecutionEvidence:
        server = self._servers.pop(receipt.provider_deployment_id, None)
        verified = False
        if server is not None:
            server[0].shutdown()
            server[0].server_close()
            server[1].join(timeout=5)
            verified = not server[1].is_alive()
        return RollbackExecutionEvidence(
            plan.canonical_fingerprint(),
            receipt.provider_deployment_id,
            server is not None,
            verified,
            "sha256:"
            + hashlib.sha256(f"{receipt.provider_deployment_id}:{verified}".encode()).hexdigest(),
        )

    def close(self) -> None:
        for provider_id, (server, thread) in tuple(self._servers.items()):
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)
            self._servers.pop(provider_id, None)

    def __enter__(self) -> LocalDeploymentProvider:
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()


__all__ = ("LocalDeploymentProvider",)
