"""Real filesystem dry-run, apply, idempotency, and reconciliation tests."""

from __future__ import annotations

import subprocess
from dataclasses import replace
from pathlib import Path

import pytest

from arch_web import (
    ApplyWorkspaceCommand,
    ExecutionOutcome,
    PrepareWorkspaceCommand,
    PrepareWorkspaceResult,
    ReconciliationStatus,
    WorkspaceChange,
    WorkspaceChangeSet,
    WorkspaceExecutionError,
    WorkspaceExecutionPolicy,
    WorkspaceExecutor,
    WorkspaceIdempotencyConflictError,
    WorkspaceOperation,
    dry_run_workspace,
    prepare_workspace,
)
from arch_web.adapters.local.filesystem import sha256_bytes
from arch_web.application.architecture.planning import semantic_id
from w05.factories import workspace_command


def _with_changes(
    command: PrepareWorkspaceCommand,
    changes: tuple[WorkspaceChange, ...],
    *,
    policy: WorkspaceExecutionPolicy | None = None,
) -> tuple[PrepareWorkspaceResult, WorkspaceExecutionPolicy]:
    prepared = prepare_workspace(command)
    change_set = WorkspaceChangeSet(
        prepared.change_set.contract_version,
        semantic_id("WCS", {"base": prepared.change_set, "changes": changes}),
        prepared.change_set.project_id,
        prepared.change_set.workspace_id,
        prepared.plan.canonical_fingerprint(),
        command.baseline.canonical_fingerprint(),
        changes,
    )
    return replace(prepared, change_set=change_set), policy or command.policy


def _file_change(
    prepared: PrepareWorkspaceResult,
    path: str,
    content: bytes,
    operation: WorkspaceOperation = WorkspaceOperation.CREATE_FILE,
    old: str | None = None,
    suffix: str = "",
) -> WorkspaceChange:
    unit = prepared.plan.units[-1]
    claim = next(item for item in prepared.plan.path_claims if item.unit_ref == unit.unit_id)
    return WorkspaceChange(
        "change:" + path.replace("/", ":") + suffix,
        operation,
        path,
        sha256_bytes(content) if operation is not WorkspaceOperation.DELETE_FILE else None,
        old,
        claim.claim_id,
        unit.unit_id,
        "Prepare neutral implementation substrate.",
    )


def test_dry_run_is_exact_and_performs_zero_mutation(tmp_path: Path) -> None:
    command = workspace_command(tmp_path)
    initial = prepare_workspace(command)
    content = b"neutral bootstrap\n"
    change = _file_change(initial, "bootstrap/README.txt", content)
    prepared, policy = _with_changes(command, (change,))
    apply_command = ApplyWorkspaceCommand(
        "execution:dry", command.target, prepared, policy, ((change.path or "", content),)
    )
    result = dry_run_workspace(apply_command)
    assert result.creates == ("bootstrap/README.txt",)
    assert not result.policy_violations
    assert not (tmp_path / "bootstrap").exists()


def test_apply_writes_safely_preserves_unknown_files_and_retries_as_same_receipt(
    tmp_path: Path,
) -> None:
    (tmp_path / "user.txt").write_text("preserve", encoding="utf-8")
    command = workspace_command(tmp_path)
    initial = prepare_workspace(command)
    content = b"bootstrap\n"
    change = _file_change(initial, "bootstrap/README.txt", content)
    prepared, policy = _with_changes(command, (change,))
    apply_command = ApplyWorkspaceCommand(
        "execution:one", command.target, prepared, policy, (("bootstrap/README.txt", content),)
    )
    executor = WorkspaceExecutor()
    first = executor.apply(apply_command)
    second = executor.apply(apply_command)
    assert first.receipt.outcome is ExecutionOutcome.APPLIED
    assert first.receipt == second.receipt
    assert (tmp_path / "bootstrap" / "README.txt").read_bytes() == content
    assert (tmp_path / "user.txt").read_text(encoding="utf-8") == "preserve"


def test_new_executor_recognizes_exact_external_noop(tmp_path: Path) -> None:
    command = workspace_command(tmp_path)
    initial = prepare_workspace(command)
    content = b"satisfied\n"
    change = _file_change(initial, "satisfied.txt", content)
    prepared, policy = _with_changes(command, (change,))
    apply_command = ApplyWorkspaceCommand(
        "external-noop", command.target, prepared, policy, (("satisfied.txt", content),)
    )
    assert WorkspaceExecutor().apply(apply_command).receipt.outcome is ExecutionOutcome.APPLIED
    replay = WorkspaceExecutor().apply(apply_command)
    assert replay.receipt.outcome is ExecutionOutcome.NOOP_ALREADY_SATISFIED


def test_stale_baseline_rejects_before_mutation(tmp_path: Path) -> None:
    command = workspace_command(tmp_path)
    initial = prepare_workspace(command)
    content = b"planned"
    change = _file_change(initial, "planned.txt", content)
    prepared, policy = _with_changes(command, (change,))
    (tmp_path / "drift.txt").write_text("user", encoding="utf-8")
    with pytest.raises(WorkspaceExecutionError, match="drifted"):
        WorkspaceExecutor().apply(
            ApplyWorkspaceCommand(
                "execution:stale", command.target, prepared, policy, (("planned.txt", content),)
            )
        )
    assert not (tmp_path / "planned.txt").exists()


def test_conflicting_execution_identity_is_rejected(tmp_path: Path) -> None:
    command = workspace_command(tmp_path)
    prepared = prepare_workspace(command)
    executor = WorkspaceExecutor()
    first = ApplyWorkspaceCommand("same", command.target, prepared, command.policy)
    executor.apply(first)
    changed = replace(prepared.change_set, change_set_id="different")
    with pytest.raises(WorkspaceIdempotencyConflictError):
        executor.apply(replace(first, prepared=replace(prepared, change_set=changed)))


def test_exact_update_precondition_and_delete_policy(tmp_path: Path) -> None:
    target = tmp_path / "existing.txt"
    target.write_bytes(b"old")
    command = workspace_command(tmp_path)
    initial = prepare_workspace(command)
    update = _file_change(
        initial, "existing.txt", b"new", WorkspaceOperation.UPDATE_FILE, sha256_bytes(b"old")
    )
    prepared, policy = _with_changes(command, (update,))
    result = WorkspaceExecutor().apply(
        ApplyWorkspaceCommand(
            "update", command.target, prepared, policy, (("existing.txt", b"new"),)
        )
    )
    assert result.receipt.outcome is ExecutionOutcome.APPLIED
    assert target.read_bytes() == b"new"

    fresh = workspace_command(tmp_path)
    initial = prepare_workspace(fresh)
    delete = _file_change(
        initial, "existing.txt", b"", WorkspaceOperation.DELETE_FILE, sha256_bytes(b"new")
    )
    prepared, policy = _with_changes(fresh, (delete,))
    with pytest.raises(WorkspaceExecutionError, match="policy"):
        WorkspaceExecutor().apply(ApplyWorkspaceCommand("delete", fresh.target, prepared, policy))

    allowed = replace(policy, allow_delete=True)
    deleted = WorkspaceExecutor().apply(
        ApplyWorkspaceCommand("delete-allowed", fresh.target, prepared, allowed)
    )
    assert deleted.receipt.outcome is ExecutionOutcome.APPLIED
    assert not target.exists()


def test_partial_failure_rolls_back_files(tmp_path: Path) -> None:
    command = workspace_command(tmp_path)
    initial = prepare_workspace(command)
    first = _file_change(initial, "one.txt", b"one", suffix=":1")
    second = _file_change(
        initial,
        "missing.txt",
        b"two",
        WorkspaceOperation.UPDATE_FILE,
        sha256_bytes(b"absent"),
        suffix=":2",
    )
    prepared, policy = _with_changes(command, (first, second))
    result = WorkspaceExecutor().apply(
        ApplyWorkspaceCommand(
            "rollback",
            command.target,
            prepared,
            policy,
            (("one.txt", b"one"), ("missing.txt", b"two")),
        )
    )
    assert result.receipt.outcome is ExecutionOutcome.FAILED_ROLLED_BACK
    assert result.receipt.reconciliation_status is ReconciliationStatus.CLEAN
    assert not (tmp_path / "one.txt").exists()


def test_directory_and_declared_git_commit_operations_are_explicit(tmp_path: Path) -> None:
    command = workspace_command(tmp_path)
    initial = prepare_workspace(command)
    unit = initial.plan.units[0].unit_id
    changes = (
        WorkspaceChange(
            "change:dir",
            WorkspaceOperation.CREATE_DIRECTORY,
            "bootstrap",
            None,
            None,
            None,
            unit,
            "Create planned neutral directory.",
        ),
        WorkspaceChange(
            "change:git",
            WorkspaceOperation.GIT_COMMIT,
            None,
            None,
            None,
            None,
            unit,
            "Record explicit future Git action.",
        ),
    )
    prepared, policy = _with_changes(command, changes)
    apply_command = ApplyWorkspaceCommand("directory", command.target, prepared, policy)
    dry = dry_run_workspace(apply_command)
    assert dry.creates == ("bootstrap/",)
    assert dry.git_actions == ("git_commit",)
    assert WorkspaceExecutor().apply(apply_command).receipt.outcome is ExecutionOutcome.APPLIED
    assert (tmp_path / "bootstrap").is_dir()


def test_dry_run_rejects_missing_or_mismatched_content(tmp_path: Path) -> None:
    command = workspace_command(tmp_path)
    initial = prepare_workspace(command)
    change = _file_change(initial, "planned.txt", b"expected")
    prepared, policy = _with_changes(command, (change,))
    missing = dry_run_workspace(ApplyWorkspaceCommand("missing", command.target, prepared, policy))
    mismatch = dry_run_workspace(
        ApplyWorkspaceCommand(
            "mismatch", command.target, prepared, policy, (("planned.txt", b"other"),)
        )
    )
    assert "missing_content:planned.txt" in missing.policy_violations
    assert "content_fingerprint:planned.txt" in mismatch.policy_violations


def test_unmanaged_create_and_stale_file_preconditions_roll_back(tmp_path: Path) -> None:
    (tmp_path / "existing.txt").write_bytes(b"user")
    command = workspace_command(tmp_path)
    initial = prepare_workspace(command)
    collision = _file_change(initial, "existing.txt", b"planned")
    prepared, policy = _with_changes(command, (collision,))
    collision_command = ApplyWorkspaceCommand(
        "collision", command.target, prepared, policy, (("existing.txt", b"planned"),)
    )
    assert (
        "unmanaged_collision:existing.txt" in dry_run_workspace(collision_command).policy_violations
    )
    with pytest.raises(WorkspaceExecutionError, match="policy"):
        WorkspaceExecutor().apply(collision_command)
    assert (tmp_path / "existing.txt").read_bytes() == b"user"

    stale = _file_change(
        initial,
        "existing.txt",
        b"planned",
        WorkspaceOperation.UPDATE_FILE,
        sha256_bytes(b"wrong"),
    )
    prepared, policy = _with_changes(command, (stale,))
    stale_result = WorkspaceExecutor().apply(
        ApplyWorkspaceCommand(
            "stale-file", command.target, prepared, policy, (("existing.txt", b"planned"),)
        )
    )
    assert stale_result.receipt.outcome is ExecutionOutcome.FAILED_ROLLED_BACK
    assert (tmp_path / "existing.txt").read_bytes() == b"user"


def test_git_init_followed_by_failure_requires_reconciliation(tmp_path: Path) -> None:
    root = tmp_path / "new"
    command = workspace_command(root, new=True)
    initial = prepare_workspace(command)
    bad = _file_change(
        initial, "missing.txt", b"new", WorkspaceOperation.UPDATE_FILE, sha256_bytes(b"old")
    )
    prepared, policy = _with_changes(command, (*initial.change_set.changes, bad))
    result = WorkspaceExecutor().apply(
        ApplyWorkspaceCommand(
            "reconcile", command.target, prepared, policy, (("missing.txt", b"new"),)
        )
    )
    assert result.receipt.outcome is ExecutionOutcome.RECONCILIATION_REQUIRED
    assert (root / ".git").exists()


def test_local_git_commit_stages_only_approved_path(tmp_path: Path) -> None:
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "test@example.invalid"], cwd=tmp_path, check=True
    )
    subprocess.run(["git", "config", "user.name", "ARCH Test"], cwd=tmp_path, check=True)
    command = workspace_command(
        tmp_path,
        policy=WorkspaceExecutionPolicy(
            create_local_commit=True, commit_message="chore: prepare workspace"
        ),
    )
    initial = prepare_workspace(command)
    change = _file_change(initial, "approved.txt", b"approved")
    prepared, policy = _with_changes(command, (change,), policy=command.policy)
    result = WorkspaceExecutor().apply(
        ApplyWorkspaceCommand(
            "commit", command.target, prepared, policy, (("approved.txt", b"approved"),)
        )
    )
    assert result.receipt.repository_evidence.after_head
    assert result.receipt.repository_evidence.clean_after


@pytest.mark.parametrize(
    ("path", "content"),
    [
        (".env", b"TOKEN=secret"),
        ("key.pem", b"private_key=secret"),
        ("safe.txt", b"api_key=secret"),
    ],
)
def test_secret_artifacts_fail_dry_run(tmp_path: Path, path: str, content: bytes) -> None:
    command = workspace_command(tmp_path)
    initial = prepare_workspace(command)
    change = _file_change(initial, path, content)
    prepared, policy = _with_changes(command, (change,))
    dry = dry_run_workspace(
        ApplyWorkspaceCommand("secret", command.target, prepared, policy, ((path, content),))
    )
    assert dry.policy_violations


def test_env_example_without_secret_is_allowed(tmp_path: Path) -> None:
    command = workspace_command(tmp_path)
    initial = prepare_workspace(command)
    content = b"API_URL=https://example.invalid\n"
    change = _file_change(initial, ".env.example", content)
    prepared, policy = _with_changes(command, (change,))
    assert not dry_run_workspace(
        ApplyWorkspaceCommand(
            "example", command.target, prepared, policy, ((".env.example", content),)
        )
    ).policy_violations
