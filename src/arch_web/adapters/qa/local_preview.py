"""Isolated loopback-only preview adapter for W08."""

from __future__ import annotations

import functools
import hashlib
import http.server
import os
import threading
import urllib.request
from dataclasses import replace
from pathlib import Path

from arch_web.application.architecture.planning import semantic_id
from arch_web.application.qa.errors import QAExecutionError
from arch_web.domain.qa import PreviewEnvironmentEvidence, PreviewPlan


class _QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, _format: str, *_args: object) -> None:
        return


class LocalPreviewSession:
    def __init__(
        self,
        server: http.server.ThreadingHTTPServer,
        thread: threading.Thread,
        evidence: PreviewEnvironmentEvidence,
    ) -> None:
        self._server = server
        self._thread = thread
        self._evidence = evidence
        self._stopped = False

    @property
    def evidence(self) -> PreviewEnvironmentEvidence:
        return self._evidence

    def stop(self) -> PreviewEnvironmentEvidence:
        if not self._stopped:
            self._server.shutdown()
            self._server.server_close()
            self._thread.join(timeout=5)
            self._stopped = True
            self._evidence = replace(
                self._evidence,
                cleanup_verified=not self._thread.is_alive(),
            )
        return self._evidence


class LocalPreviewAdapter:
    """Serves an exact candidate directory without modifying product source."""

    identity = "arch-web.local-preview@0.1.0"

    def start(self, plan: PreviewPlan) -> LocalPreviewSession:
        root = Path(plan.workspace_root).resolve()
        entrypoint = (root / plan.entrypoint_path).resolve()
        if root not in entrypoint.parents or not entrypoint.is_file():
            raise QAExecutionError("Preview entrypoint is missing or outside workspace")
        if (
            plan.application_database_path is not None
            and plan.runtime_database_path is not None
            and Path(plan.application_database_path).resolve()
            == Path(plan.runtime_database_path).resolve()
        ):
            raise QAExecutionError("Preview application database cannot reuse Runtime database")
        handler = functools.partial(_QuietHandler, directory=str(entrypoint.parent))
        server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
        thread = threading.Thread(target=server.serve_forever, name="arch-web-preview", daemon=True)
        thread.start()
        endpoint = f"http://127.0.0.1:{server.server_port}/"
        ready = False
        try:
            with urllib.request.urlopen(
                endpoint, timeout=plan.readiness_timeout_seconds
            ) as response:
                ready = response.status == 200 and b"<!doctype html>" in response.read(4096).lower()
        except OSError:
            ready = False
        digest = (
            "sha256:" + hashlib.sha256(f"{self.identity}:{endpoint}:{ready}".encode()).hexdigest()
        )
        evidence = PreviewEnvironmentEvidence(
            semantic_id("PVE", {"plan": plan, "endpoint": endpoint, "ready": ready}),
            plan.candidate_fingerprint,
            endpoint,
            self.identity,
            os.getpid(),
            "sha256:" + hashlib.sha256(plan.fixture_id.encode()).hexdigest(),
            ready,
            digest,
            False,
        )
        return LocalPreviewSession(server, thread, evidence)


__all__ = ("LocalPreviewAdapter", "LocalPreviewSession")
