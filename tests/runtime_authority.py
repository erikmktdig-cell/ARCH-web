"""Public Runtime authority doubles shared by Web bridge tests."""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

from arch_kernel.contracts import ProjectId, WorkflowStateKey
from arch_kernel.kernel import initialize_workflow_state

from arch_web import WEB_WORKFLOW_DEFINITION, WebLifecycleStatus


def runtime_project(
    status: WebLifecycleStatus,
    *,
    project_id: str,
    record_version: int,
    record_fingerprint: str,
    content_fingerprint: str,
) -> SimpleNamespace:
    """Build the minimal public get-project evidence consumed by Web bridges."""

    record = initialize_workflow_state(
        WEB_WORKFLOW_DEFINITION,
        created_at=datetime(2026, 9, 2, tzinfo=UTC),
        state_version_created=record_version,
    ).model_copy(update={"current_state": WorkflowStateKey.parse(status.value)})
    return SimpleNamespace(
        project_id=ProjectId(project_id),
        state=SimpleNamespace(workflow_registry={WEB_WORKFLOW_DEFINITION.workflow_id: record}),
        record_version=record_version,
        record_fingerprint=record_fingerprint,
        content_fingerprint=content_fingerprint,
    )
