"""Real Kernel, Runtime SQLite, and Web bridge lifecycle integration."""

from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path
from typing import cast

import pytest
from arch_kernel.contracts import ProjectId, Route
from arch_kernel.kernel import InvariantRegistry
from arch_runtime import (
    ApplyTransitionCommand,
    ApplyTransitionResult,
    CreateProjectCommand,
    CreateProjectResult,
    IdempotencyConflictError,
    Runtime,
    RuntimeConfig,
)

from arch_web import (
    WEB_TRANSITION_REGISTRY,
    WEB_WORKFLOW_DEFINITION_REGISTRY,
    ApproveDeploymentCommand,
    AuthorizeDeploymentCommand,
    EvidenceRef,
    ExecuteDeploymentCommand,
    InitializeWebLifecycleCommand,
    LocalDeploymentProvider,
    QAStatus,
    VerifyDeploymentCommand,
    WebLifecycleStatus,
    approve_architecture,
    approve_deployment,
    approve_implementation_readiness,
    approve_release_readiness,
    approve_requirements,
    approve_ui_specification,
    authorize_deployment,
    authorize_frontend,
    authorize_testing,
    execute_deployment,
    initialize_web_lifecycle,
    prepare_release,
    read_web_lifecycle,
    verify_deployment,
)
from arch_web.application.architecture.errors import ArchitectureApprovalError
from arch_web.application.requirements.errors import RequirementsApprovalError
from w02.factories import PROJECT_ID
from w02.test_approval_bridge import approval_command as requirements_command
from w03.test_approval import approval_command as architecture_command
from w04.test_approval import approval_command as ui_command
from w05.test_runtime import approval_command as workspace_command
from w06.test_authorization import authorization_command as frontend_command
from w08.factories import qa_bundle
from w08.fakes import SequencedBrowser
from w08.test_aggregation import _execute
from w08.test_runtime_bridge import _authorize_command, _release_command
from w09.factories import prepare_command, provider, target


class FixedProjectIds:
    def new(self) -> ProjectId:
        return ProjectId(PROJECT_ID)


class RecordingRuntime:
    def __init__(self, runtime: Runtime) -> None:
        self.runtime = runtime
        self.commands: list[ApplyTransitionCommand] = []

    def get_project(self, project_id: ProjectId) -> object:
        return self.runtime.get_project(project_id)

    def apply_transition(self, command: ApplyTransitionCommand) -> ApplyTransitionResult:
        self.commands.append(command)
        return self.runtime.apply_transition(command)


@dataclass(frozen=True, slots=True)
class RuntimeFields:
    record_version: int
    record_fingerprint: str
    content_fingerprint: str
    workflow_record_version: int
    workflow_content_fingerprint: str

    def changes(self) -> dict[str, object]:
        return {
            "expected_record_version": self.record_version,
            "expected_record_fingerprint": self.record_fingerprint,
            "expected_content_fingerprint": self.content_fingerprint,
            "expected_workflow_record_version": self.workflow_record_version,
            "expected_workflow_content_fingerprint": self.workflow_content_fingerprint,
        }


def _create(runtime: Runtime) -> CreateProjectResult:
    return runtime.create_project(
        CreateProjectCommand.model_validate(
            {
                "idempotency_key": "c03:project:create",
                "name": "C03 Web Lifecycle",
                "slug": "c03-web-lifecycle",
                "summary": "Exercise every governed Web lifecycle bridge.",
                "owner": "arch-web",
                "project_type": "web",
                "criticality": "medium",
                "default_route": Route.QUICK,
                "objectives": ("Prove cross-stack compatibility.",),
                "constraints": ("Use public APIs only.",),
                "success_criteria": ("Reach DEPLOYED with verified evidence.",),
                "actor_id": "user:c03",
            },
            strict=True,
        )
    )


def _assert_state(
    runtime: Runtime,
    status: WebLifecycleStatus,
    *,
    aggregate_version: int,
    workflow_version: int,
    event_count: int,
) -> None:
    evidence = read_web_lifecycle(runtime, PROJECT_ID)
    replay = runtime.replay_project(ProjectId(PROJECT_ID))
    assert evidence.current_status is status
    assert evidence.aggregate_record_version == aggregate_version
    assert evidence.workflow_record_version == workflow_version
    assert replay.event_count == event_count
    assert replay.record_version == aggregate_version
    assert replay.record_fingerprint == evidence.aggregate_record_fingerprint
    assert replay.content_fingerprint == evidence.aggregate_content_fingerprint


def _runtime_fields(runtime: Runtime) -> RuntimeFields:
    evidence = read_web_lifecycle(runtime, PROJECT_ID)
    return RuntimeFields(
        evidence.aggregate_record_version,
        evidence.aggregate_record_fingerprint,
        evidence.aggregate_content_fingerprint,
        evidence.workflow_record_version,
        evidence.workflow_content_fingerprint,
    )


def test_real_sqlite_executes_the_complete_web_lifecycle(tmp_path: Path) -> None:
    database = tmp_path / "c03-runtime.db"
    with Runtime.open(
        RuntimeConfig(
            database,
            initialize_schema=True,
            project_ids=FixedProjectIds(),
            transition_registry=WEB_TRANSITION_REGISTRY,
            workflow_definition_registry=WEB_WORKFLOW_DEFINITION_REGISTRY,
            invariant_registry=InvariantRegistry(()),
        )
    ) as runtime:
        created = _create(runtime)
        assert created.record_version is not None
        assert created.record_fingerprint is not None
        assert created.content_fingerprint is not None
        before_init = requirements_command(**_runtime_fields_from_created(created))
        with pytest.raises(RequirementsApprovalError, match="not initialized"):
            approve_requirements(runtime, before_init)

        initialized = initialize_web_lifecycle(
            runtime,
            InitializeWebLifecycleCommand(
                project_id=PROJECT_ID,
                idempotency_key="c03:web-workflow:init",
                expected_record_version=created.record_version,
                expected_record_fingerprint=created.record_fingerprint,
                expected_content_fingerprint=created.content_fingerprint,
                actor_id="user:c03",
            ),
        )
        assert initialized.success
        assert initialized.changed
        _assert_state(
            runtime,
            WebLifecycleStatus.DRAFT,
            aggregate_version=2,
            workflow_version=1,
            event_count=2,
        )

        recording = RecordingRuntime(runtime)
        bridge_runtime = cast(Runtime, recording)
        requirements = requirements_command(**_runtime_fields(runtime).changes())
        first_requirements = approve_requirements(bridge_runtime, requirements)
        assert first_requirements.approved, first_requirements.runtime_result.model_dump_json()
        _assert_state(
            runtime,
            WebLifecycleStatus.REQUIREMENTS_APPROVED,
            aggregate_version=3,
            workflow_version=2,
            event_count=3,
        )
        assert approve_requirements(bridge_runtime, requirements) == first_requirements
        _assert_state(
            runtime,
            WebLifecycleStatus.REQUIREMENTS_APPROVED,
            aggregate_version=3,
            workflow_version=2,
            event_count=3,
        )
        with pytest.raises(IdempotencyConflictError):
            approve_requirements(
                bridge_runtime, replace(requirements, actor_display_name="Changed reviewer")
            )

        architecture = architecture_command(**_runtime_fields(runtime).changes())
        with pytest.raises(ArchitectureApprovalError, match="workflow evidence is stale"):
            approve_architecture(
                bridge_runtime,
                replace(architecture, expected_workflow_record_version=99),
            )
        assert approve_architecture(bridge_runtime, architecture).approved
        _assert_state(
            runtime,
            WebLifecycleStatus.ARCHITECTURE_APPROVED,
            aggregate_version=4,
            workflow_version=3,
            event_count=4,
        )

        ui = ui_command(**_runtime_fields(runtime).changes())
        assert approve_ui_specification(bridge_runtime, ui).approved
        _assert_state(
            runtime,
            WebLifecycleStatus.UI_APPROVED,
            aggregate_version=5,
            workflow_version=4,
            event_count=5,
        )

        workspace_root = tmp_path / "workspace"
        workspace_root.mkdir()
        workspace = workspace_command(workspace_root, **_runtime_fields(runtime).changes())
        assert approve_implementation_readiness(bridge_runtime, workspace).approved
        _assert_state(
            runtime,
            WebLifecycleStatus.IMPLEMENTATION_READY,
            aggregate_version=6,
            workflow_version=5,
            event_count=6,
        )

        frontend_root = tmp_path / "frontend"
        frontend_root.mkdir()
        frontend = frontend_command(frontend_root)
        fields = _runtime_fields(runtime)
        assignment = replace(
            frontend.prepared.assignment,
            runtime_record_version=fields.record_version,
            runtime_record_fingerprint=fields.record_fingerprint,
        )
        frontend = replace(
            frontend,
            prepared=replace(frontend.prepared, assignment=assignment),
            expected_assignment_fingerprint=assignment.canonical_fingerprint(),
            expected_record_version=fields.record_version,
            expected_record_fingerprint=fields.record_fingerprint,
            expected_content_fingerprint=fields.content_fingerprint,
            expected_workflow_record_version=fields.workflow_record_version,
            expected_workflow_content_fingerprint=fields.workflow_content_fingerprint,
        )
        assert authorize_frontend(bridge_runtime, frontend).authorization.authorized
        _assert_state(
            runtime,
            WebLifecycleStatus.IMPLEMENTING,
            aggregate_version=7,
            workflow_version=6,
            event_count=7,
        )

        qa_root = tmp_path / "qa"
        qa_root.mkdir()
        _, prepared, profile = qa_bundle(qa_root)
        fields = _runtime_fields(runtime)
        candidate = replace(
            prepared.candidate,
            runtime_record_version=fields.record_version,
            runtime_record_fingerprint=fields.record_fingerprint,
        )
        prepared = replace(
            prepared,
            candidate=candidate,
            scope=replace(prepared.scope, candidate_fingerprint=candidate.canonical_fingerprint()),
        )
        testing = _authorize_command(prepared, **fields.changes())
        assert authorize_testing(bridge_runtime, testing).authorization.authorized
        _assert_state(
            runtime,
            WebLifecycleStatus.TESTING,
            aggregate_version=8,
            workflow_version=7,
            event_count=8,
        )

        executed = _execute(prepared, profile, SequencedBrowser((QAStatus.PASS,)))
        release_ready = _release_command(prepared, executed, **_runtime_fields(runtime).changes())
        release_result = approve_release_readiness(bridge_runtime, release_ready)
        assert release_result.runtime_result.success
        _assert_state(
            runtime,
            WebLifecycleStatus.RELEASE_READY,
            aggregate_version=9,
            workflow_version=8,
            event_count=9,
        )

        release_root = tmp_path / "release"
        release_root.mkdir()
        source = prepare_command(release_root)
        fields = _runtime_fields(runtime)
        assert source.release_version is not None
        source = replace(
            source,
            runtime_record_version=fields.record_version,
            runtime_record_fingerprint=fields.record_fingerprint,
            release_readiness=release_result.package,
            release_version=replace(
                source.release_version,
                source_commit=release_result.package.git_head,
                source_tree_fingerprint=release_result.package.source_tree_fingerprint,
            ),
        )
        prepared_release = prepare_release(source)
        deployment_authorization = authorize_deployment(
            AuthorizeDeploymentCommand(
                prepared_release,
                target(),
                provider(),
                None,
                "c03:deploy:authorize",
                "deployment:previous",
                (EvidenceRef("approval:c03-deploy", "human-approval", "urn:c03:deploy"),),
            )
        ).authorization
        adapter = LocalDeploymentProvider(tmp_path / "deployments")
        try:
            receipt = execute_deployment(
                ExecuteDeploymentCommand(
                    prepared_release,
                    deployment_authorization,
                    source.artifacts[0],
                    source.target,
                    source.config,
                    None,
                ),
                adapter,
            ).receipt
            verification = verify_deployment(
                VerifyDeploymentCommand(prepared_release, receipt, source.target), adapter
            )
            deployment = approve_deployment(
                bridge_runtime,
                _deployment_command(
                    prepared_release,
                    deployment_authorization,
                    receipt,
                    verification,
                    source.target,
                    fields,
                ),
            )
            assert deployment.runtime_result.success
        finally:
            adapter.close()
        _assert_state(
            runtime,
            WebLifecycleStatus.DEPLOYED,
            aggregate_version=10,
            workflow_version=9,
            event_count=10,
        )
        assert len(recording.commands) == 10
        assert all(
            isinstance(key, str) and isinstance(value, str)
            for command in recording.commands
            for key, value in command.metadata.items()
        )


def _runtime_fields_from_created(created: CreateProjectResult) -> dict[str, object]:
    assert created.record_version is not None
    assert created.record_fingerprint is not None
    assert created.content_fingerprint is not None
    return {
        "expected_record_version": created.record_version,
        "expected_record_fingerprint": created.record_fingerprint,
        "expected_content_fingerprint": created.content_fingerprint,
    }


def _deployment_command(
    prepared: object,
    authorization: object,
    receipt: object,
    verification: object,
    deployment_target: object,
    fields: RuntimeFields,
) -> ApproveDeploymentCommand:
    return ApproveDeploymentCommand(
        project_status=WebLifecycleStatus.RELEASE_READY,
        prepared=prepared,  # type: ignore[arg-type]
        authorization=authorization,  # type: ignore[arg-type]
        receipt=receipt,  # type: ignore[arg-type]
        verification=verification,  # type: ignore[arg-type]
        target=deployment_target,  # type: ignore[arg-type]
        approval_evidence=(
            EvidenceRef("approval:c03-final", "human-final-deployment", "urn:c03:final"),
        ),
        idempotency_key="c03:deployment:approve",
        request_id="CHG-01HZX7M3FQ1T2Q9V8Y6K4C2R07",
        transition_key="web.release.deployed",
        expected_runtime_state="RELEASE_READY",
        expected_record_version=fields.record_version,
        expected_record_fingerprint=fields.record_fingerprint,
        expected_content_fingerprint=fields.content_fingerprint,
        actor_id="user:c03-release",
        actor_display_name="C03 Release Reviewer",
        expected_workflow_record_version=fields.workflow_record_version,
        expected_workflow_content_fingerprint=fields.workflow_content_fingerprint,
    )
