"""Runtime-governed IMPLEMENTATION_READY to IMPLEMENTING authorization."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from typing import cast

import pytest
from arch_runtime import ApplyTransitionCommand, ApplyTransitionResult, Runtime

from arch_web import (
    AuthorizeFrontendCommand,
    EvidenceRef,
    FrontendAuthorizationError,
    WebLifecycleStatus,
    authorize_frontend,
)
from w02.factories import REQUEST_ID
from w06.factories import prepared_frontend


def _result(success: bool) -> ApplyTransitionResult:
    return cast(ApplyTransitionResult, SimpleNamespace(success=success))


class FakeRuntime:
    def __init__(self, success: bool = True) -> None:
        self.result = _result(success)
        self.commands: list[ApplyTransitionCommand] = []
        self.saved: dict[str, tuple[dict[str, object], ApplyTransitionResult]] = {}

    def apply_transition(self, command: ApplyTransitionCommand) -> ApplyTransitionResult:
        payload = command.request_payload()
        previous = self.saved.get(command.idempotency_key)
        if previous is not None:
            if previous[0] != payload:
                raise RuntimeError("idempotency conflict")
            return previous[1]
        self.commands.append(command)
        self.saved[command.idempotency_key] = (payload, self.result)
        return self.result


def authorization_command(root: Path, **changes: object) -> AuthorizeFrontendCommand:
    *_, command, prepared = prepared_frontend(root)
    values: dict[str, object] = {
        "prepared": prepared,
        "project_status": WebLifecycleStatus.IMPLEMENTATION_READY,
        "expected_assignment_fingerprint": prepared.assignment.canonical_fingerprint(),
        "approval_evidence": EvidenceRef(
            "approval:w06", "human-frontend-authorization", "urn:approval:w06"
        ),
        "idempotency_key": "web:frontend:authorize:1",
        "request_id": REQUEST_ID,
        "transition_key": "web.frontend.implementing",
        "expected_runtime_state": "implementation_ready",
        "expected_record_version": command.runtime_record_version,
        "expected_record_fingerprint": command.runtime_record_fingerprint,
        "expected_content_fingerprint": "sha256:" + "b" * 64,
        "actor_id": "user:frontend-reviewer",
        "actor_display_name": "Frontend Reviewer",
    }
    values.update(changes)
    return AuthorizeFrontendCommand(**values)  # type: ignore[arg-type]


def test_runtime_authorizes_before_any_source_mutation(tmp_path: Path) -> None:
    runtime = FakeRuntime()
    before = tuple(tmp_path.rglob("*"))
    result = authorize_frontend(cast(Runtime, runtime), authorization_command(tmp_path))
    assert result.authorization.authorized
    assert tuple(tmp_path.rglob("*")) == before
    metadata = runtime.commands[0].metadata
    assert metadata["web_transition"] == "IMPLEMENTATION_READY->IMPLEMENTING"
    assert metadata["blocking_finding_count"] == 0


def test_runtime_rejection_is_preserved_as_unauthorized(tmp_path: Path) -> None:
    result = authorize_frontend(cast(Runtime, FakeRuntime(False)), authorization_command(tmp_path))
    assert not result.authorization.authorized


def test_exact_retry_is_idempotent(tmp_path: Path) -> None:
    runtime = FakeRuntime()
    command = authorization_command(tmp_path)
    assert authorize_frontend(cast(Runtime, runtime), command) == authorize_frontend(
        cast(Runtime, runtime), command
    )
    assert len(runtime.commands) == 1


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"project_status": WebLifecycleStatus.UI_APPROVED}, "IMPLEMENTATION_READY"),
        ({"expected_assignment_fingerprint": "stale"}, "assignment"),
        ({"expected_record_version": 99}, "version"),
        ({"expected_record_fingerprint": "stale"}, "fingerprint"),
    ],
)
def test_stale_authorization_fails_before_runtime(
    tmp_path: Path, changes: dict[str, object], message: str
) -> None:
    runtime = FakeRuntime()
    with pytest.raises(FrontendAuthorizationError, match=message):
        authorize_frontend(cast(Runtime, runtime), authorization_command(tmp_path, **changes))
    assert not runtime.commands


def test_conflicting_idempotency_is_not_hidden(tmp_path: Path) -> None:
    runtime = FakeRuntime()
    command = authorization_command(tmp_path)
    authorize_frontend(cast(Runtime, runtime), command)
    with pytest.raises(RuntimeError, match="idempotency"):
        authorize_frontend(
            cast(Runtime, runtime), replace(command, actor_display_name="Other Reviewer")
        )
