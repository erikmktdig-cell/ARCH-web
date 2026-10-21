"""Canonical Web workflow and Runtime boundary tests."""

from __future__ import annotations

from typing import cast

import pytest
from arch_kernel.contracts import WorkflowId, WorkflowNamespace, WorkflowStateKey
from arch_kernel.kernel import TransitionRegistry
from arch_runtime import Runtime
from hypothesis import given
from hypothesis import strategies as st

from arch_web import (
    WEB_TRANSITION_DEFINITIONS,
    WEB_TRANSITION_REGISTRY,
    WEB_WORKFLOW_DEFINITION,
    WEB_WORKFLOW_ID,
    WEB_WORKFLOW_NAMESPACE,
    WebLifecycleStatus,
    WebWorkflowAuthorityError,
    read_web_lifecycle,
)
from arch_web.contracts.canonical import JsonValue
from arch_web.runtime_bridge.runtime_metadata import (
    build_runtime_metadata,
    metadata_canonical_json,
    metadata_integer,
    metadata_string,
)
from arch_web.runtime_bridge.workflow import build_web_transition_command
from runtime_authority import runtime_project
from w02.factories import PROJECT_ID, REQUEST_ID


class ReadRuntime:
    def __init__(self, project: object) -> None:
        self.project = project

    def get_project(self, project_id: object) -> object:
        return self.project


def _runtime(status: WebLifecycleStatus = WebLifecycleStatus.DRAFT) -> ReadRuntime:
    return ReadRuntime(
        runtime_project(
            status,
            project_id=PROJECT_ID,
            record_version=2,
            record_fingerprint="sha256:" + "a" * 64,
            content_fingerprint="sha256:" + "b" * 64,
        )
    )


def _transition(runtime: ReadRuntime, destination: WebLifecycleStatus) -> object:
    evidence = read_web_lifecycle(cast(Runtime, runtime), PROJECT_ID)
    return build_web_transition_command(
        cast(Runtime, runtime),
        project_id=PROJECT_ID,
        asserted_status=evidence.current_status,
        asserted_runtime_state=evidence.current_status.value,
        destination=destination,
        transition_key={
            WebLifecycleStatus.REQUIREMENTS_APPROVED: "web.requirements_approve",
            WebLifecycleStatus.UI_APPROVED: "web.ui_approve",
        }[destination],
        idempotency_key="c03:test:transition",
        request_id=REQUEST_ID,
        expected_record_version=evidence.aggregate_record_version,
        expected_record_fingerprint=evidence.aggregate_record_fingerprint,
        expected_content_fingerprint=evidence.aggregate_content_fingerprint,
        expected_workflow_record_version=evidence.workflow_record_version,
        expected_workflow_content_fingerprint=evidence.workflow_content_fingerprint,
        metadata={"source": "c03"},
        actor_id="user:c03",
        actor_display_name=None,
    )


def test_web_workflow_is_closed_deterministic_and_exact() -> None:
    assert WorkflowNamespace.parse("arch_web.project_lifecycle") == WEB_WORKFLOW_NAMESPACE
    assert WEB_WORKFLOW_DEFINITION.workflow_id == WEB_WORKFLOW_ID
    assert {str(item) for item in WEB_WORKFLOW_DEFINITION.allowed_states} == {
        item.value for item in WebLifecycleStatus
    }
    assert len(WEB_WORKFLOW_DEFINITION.allowed_states) == len(WebLifecycleStatus)
    assert str(WEB_WORKFLOW_DEFINITION.initial_state) == WebLifecycleStatus.DRAFT.value
    assert WEB_WORKFLOW_DEFINITION.definition_fingerprint() == (
        "sha256:535d3d0a0d575d7a9b4ccd937a7001a28e7cbe9a34a9fe4cb2c1fd28e5ae4a80"
    )
    assert len(WEB_TRANSITION_DEFINITIONS) == 8
    assert len(WEB_TRANSITION_REGISTRY.definitions) == 8


def test_transition_registry_is_order_independent() -> None:
    reversed_registry = TransitionRegistry(
        tuple(reversed(WEB_TRANSITION_DEFINITIONS)),
        workflow_definitions=(WEB_WORKFLOW_DEFINITION,),
    )
    assert reversed_registry.definitions == WEB_TRANSITION_REGISTRY.definitions


@given(st.dictionaries(st.text(min_size=1), st.integers(), max_size=8))
def test_metadata_canonicalization_is_deterministic(value: dict[str, int]) -> None:
    left = metadata_canonical_json(cast(JsonValue, value))
    right = metadata_canonical_json(cast(JsonValue, dict(reversed(tuple(value.items())))))
    assert left == right


def test_metadata_helpers_are_string_only_and_omit_absent_values() -> None:
    metadata = build_runtime_metadata(
        strings={"id": "item-1", "optional": None},
        integers={"count": 3},
        structured={"evidence": {"items": [2, 1], "valid": True}},
    )
    assert metadata == {
        "count": "3",
        "evidence": '{"items":[2,1],"valid":true}',
        "id": "item-1",
    }
    assert all(isinstance(key, str) and isinstance(value, str) for key, value in metadata.items())
    assert metadata_string("x") == "x"
    assert metadata_integer(0) == "0"
    with pytest.raises((TypeError, ValueError)):
        metadata_integer(cast(int, True))
    with pytest.raises((TypeError, ValueError)):
        metadata_string(" x ")


def test_runtime_authority_cannot_be_overridden_or_skipped() -> None:
    runtime = _runtime()
    with pytest.raises(WebWorkflowAuthorityError, match="Caller lifecycle"):
        _transition(runtime, WebLifecycleStatus.UI_APPROVED)
    evidence = read_web_lifecycle(cast(Runtime, runtime), PROJECT_ID)
    with pytest.raises(WebWorkflowAuthorityError, match="Caller lifecycle"):
        build_web_transition_command(
            cast(Runtime, runtime),
            project_id=PROJECT_ID,
            asserted_status=WebLifecycleStatus.REQUIREMENTS_APPROVED,
            asserted_runtime_state=WebLifecycleStatus.REQUIREMENTS_APPROVED.value,
            destination=WebLifecycleStatus.ARCHITECTURE_APPROVED,
            transition_key="web.architecture_approve",
            idempotency_key="c03:test:override",
            request_id=REQUEST_ID,
            expected_record_version=evidence.aggregate_record_version,
            expected_record_fingerprint=evidence.aggregate_record_fingerprint,
            expected_content_fingerprint=evidence.aggregate_content_fingerprint,
            expected_workflow_record_version=evidence.workflow_record_version,
            expected_workflow_content_fingerprint=evidence.workflow_content_fingerprint,
            metadata={"source": "c03"},
            actor_id="user:c03",
            actor_display_name=None,
        )


@pytest.mark.parametrize("corruption", ["id", "namespace", "fingerprint", "state"])
def test_invalid_workflow_binding_fails_closed(corruption: str) -> None:
    project = runtime_project(
        WebLifecycleStatus.DRAFT,
        project_id=PROJECT_ID,
        record_version=2,
        record_fingerprint="sha256:" + "a" * 64,
        content_fingerprint="sha256:" + "b" * 64,
    )
    original = project.state.workflow_registry[WEB_WORKFLOW_ID]
    if corruption == "id":
        changed = original.model_copy(
            update={"workflow_id": WorkflowId.from_str("WFL-01HZX7M3FQ1T2Q9V8Y6K4C2B1B")}
        )
    elif corruption == "namespace":
        changed = original.model_copy(
            update={"namespace": WorkflowNamespace.parse("arch_web.wrong")}
        )
    elif corruption == "fingerprint":
        changed = original.model_copy(update={"definition_fingerprint": "sha256:" + "9" * 64})
    else:
        changed = original.model_copy(update={"current_state": WorkflowStateKey.parse("UNKNOWN")})
    project.state.workflow_registry[WEB_WORKFLOW_ID] = changed
    with pytest.raises(WebWorkflowAuthorityError, match="binding"):
        read_web_lifecycle(cast(Runtime, ReadRuntime(project)), PROJECT_ID)


def test_missing_workflow_never_auto_initializes() -> None:
    project = runtime_project(
        WebLifecycleStatus.DRAFT,
        project_id=PROJECT_ID,
        record_version=1,
        record_fingerprint="sha256:" + "a" * 64,
        content_fingerprint="sha256:" + "b" * 64,
    )
    project.state.workflow_registry.clear()
    with pytest.raises(WebWorkflowAuthorityError, match="not initialized"):
        read_web_lifecycle(cast(Runtime, ReadRuntime(project)), PROJECT_ID)
