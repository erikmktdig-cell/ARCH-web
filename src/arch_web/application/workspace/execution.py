"""W05 mutation-free dry-run and governed external workspace execution."""

from __future__ import annotations

import re
from pathlib import Path

from arch_web.adapters.local.filesystem import LocalFileSystem, sha256_bytes
from arch_web.adapters.local.git import LocalGit
from arch_web.adapters.local.lock import LocalWorkspaceLocks
from arch_web.application.workspace.errors import (
    WorkspaceExecutionError,
    WorkspaceIdempotencyConflictError,
)
from arch_web.application.workspace.models import ApplyWorkspaceCommand, ApplyWorkspaceResult
from arch_web.contracts.versions import CURRENT_WEB_CONTRACT_VERSION
from arch_web.domain.workspace import (
    ExecutionOutcome,
    FileEvidence,
    ReconciliationStatus,
    RepositoryEvidence,
    WorkspaceDryRun,
    WorkspaceExecutionReceipt,
    WorkspaceOperation,
)
from arch_web.workspace_paths import normalize_managed_path

_SECRET_PATH = re.compile(r"(?i)(^|/)(\.env$|\.npmrc$|id_rsa$|.*\.(pem|key)$)")
_SECRET_CONTENT = re.compile(rb"(?i)(api[_-]?key|token|password|private[_-]?key)\s*[:=]\s*[^\s#]+")


def _content_map(command: ApplyWorkspaceCommand) -> dict[str, bytes]:
    return {normalize_managed_path(path): content for path, content in command.contents}


def dry_run_workspace(command: ApplyWorkspaceCommand) -> WorkspaceDryRun:
    contents = _content_map(command)
    creates: list[str] = []
    updates: list[str] = []
    deletes: list[str] = []
    git_actions: list[str] = []
    violations: list[str] = []
    baseline_paths = {item.path for item in command.prepared.baseline.files}
    for change in command.prepared.change_set.changes:
        path = None if change.path is None else normalize_managed_path(change.path)
        if change.operation is WorkspaceOperation.CREATE_FILE:
            if path is not None:
                creates.append(path)
                if path in baseline_paths:
                    violations.append(f"unmanaged_collision:{path}")
        elif change.operation is WorkspaceOperation.CREATE_DIRECTORY:
            if path is not None:
                creates.append(path + "/")
        elif change.operation is WorkspaceOperation.UPDATE_FILE:
            if path is not None:
                updates.append(path)
        elif change.operation is WorkspaceOperation.DELETE_FILE:
            if path is not None:
                deletes.append(path)
            if not command.policy.allow_delete:
                violations.append("delete_not_allowed")
        elif change.operation in {WorkspaceOperation.GIT_INIT, WorkspaceOperation.GIT_COMMIT}:
            git_actions.append(change.operation.value)
        if path is not None and _SECRET_PATH.search(path) and path != ".env.example":
            violations.append(f"secret_path:{path}")
        if path is not None and path in contents:
            content = contents[path]
            if _SECRET_CONTENT.search(content):
                violations.append(f"secret_content:{path}")
            if (
                change.new_fingerprint is not None
                and sha256_bytes(content) != change.new_fingerprint
            ):
                violations.append(f"content_fingerprint:{path}")
        if (
            change.operation in {WorkspaceOperation.CREATE_FILE, WorkspaceOperation.UPDATE_FILE}
            and path not in contents
        ):
            violations.append(f"missing_content:{path}")
    return WorkspaceDryRun(
        command.prepared.change_set.canonical_fingerprint(),
        tuple(creates),
        tuple(updates),
        tuple(deletes),
        tuple(git_actions),
        tuple(violations),
        None,
    )


class WorkspaceExecutor:
    def __init__(self, *, locks: LocalWorkspaceLocks | None = None) -> None:
        self.locks = locks or LocalWorkspaceLocks()
        self._receipts: dict[str, tuple[str, WorkspaceExecutionReceipt]] = {}

    def apply(self, command: ApplyWorkspaceCommand) -> ApplyWorkspaceResult:
        fingerprint = command.prepared.change_set.canonical_fingerprint()
        previous = self._receipts.get(command.execution_id)
        if previous is not None:
            if previous[0] != fingerprint:
                raise WorkspaceIdempotencyConflictError(
                    "Execution identity already binds another change set"
                )
            return ApplyWorkspaceResult(dry_run_workspace(command), previous[1])
        dry_run = dry_run_workspace(command)
        if dry_run.policy_violations:
            raise WorkspaceExecutionError("Dry-run contains blocking policy violations")
        root = Path(command.target.root_path)
        filesystem = LocalFileSystem(root, command.prepared.baseline.toolchain_capabilities)
        git = LocalGit(root)
        with self.locks.acquire(root, command.execution_id):
            before_repo = git.inspect()
            before = filesystem.inspect(command.target, before_repo)
            if before.canonical_fingerprint() != command.prepared.change_set.baseline_fingerprint:
                if self._already_satisfied(command, filesystem):
                    receipt = self._receipt(
                        command,
                        before,
                        before,
                        before_repo,
                        before_repo,
                        (),
                        ExecutionOutcome.NOOP_ALREADY_SATISFIED,
                        ReconciliationStatus.CLEAN,
                    )
                    self._receipts[command.execution_id] = (fingerprint, receipt)
                    return ApplyWorkspaceResult(dry_run, receipt)
                raise WorkspaceExecutionError("Workspace baseline drifted before mutation")
            receipt = self._execute(command, filesystem, git, before, before_repo)
            self._receipts[command.execution_id] = (fingerprint, receipt)
            return ApplyWorkspaceResult(dry_run, receipt)

    @staticmethod
    def _already_satisfied(command: ApplyWorkspaceCommand, filesystem: LocalFileSystem) -> bool:
        for change in command.prepared.change_set.changes:
            if change.operation in {WorkspaceOperation.CREATE_FILE, WorkspaceOperation.UPDATE_FILE}:
                if change.path is None or not filesystem.exists(change.path):
                    return False
                if sha256_bytes(filesystem.read_bytes(change.path)) != change.new_fingerprint:
                    return False
            elif change.operation is WorkspaceOperation.DELETE_FILE:
                if change.path is not None and filesystem.exists(change.path):
                    return False
            elif change.operation is WorkspaceOperation.GIT_INIT:
                if not (filesystem.root / ".git").exists():
                    return False
            elif change.operation is WorkspaceOperation.CREATE_DIRECTORY:
                if change.path is None or not filesystem.exists(change.path):
                    return False
        return bool(command.prepared.change_set.changes)

    def _execute(
        self,
        command: ApplyWorkspaceCommand,
        filesystem: LocalFileSystem,
        git: LocalGit,
        before: object,
        before_repo: object,
    ) -> WorkspaceExecutionReceipt:
        from arch_web.domain.workspace import RepositoryBaseline, WorkspaceBaseline

        assert isinstance(before, WorkspaceBaseline)
        assert isinstance(before_repo, RepositoryBaseline)
        contents = _content_map(command)
        originals: dict[str, bytes | None] = {}
        created_directories: list[str] = []
        changed: list[str] = []
        git_mutated = False
        try:
            for change in command.prepared.change_set.changes:
                path = change.path
                if change.operation is WorkspaceOperation.GIT_INIT:
                    git.initialize()
                    git_mutated = True
                    continue
                if change.operation is WorkspaceOperation.GIT_COMMIT:
                    continue
                if path is None:
                    raise WorkspaceExecutionError("Filesystem change requires path")
                existed = filesystem.exists(path)
                old = filesystem.read_bytes(path) if existed else None
                originals[path] = old
                if change.operation is WorkspaceOperation.CREATE_DIRECTORY:
                    filesystem.create_directory(path)
                    originals.pop(path)
                    if not existed:
                        created_directories.append(path)
                    continue
                elif change.operation is WorkspaceOperation.CREATE_FILE:
                    if existed:
                        raise WorkspaceExecutionError("Unmanaged create collision")
                    filesystem.write_bytes(path, contents[path])
                elif change.operation is WorkspaceOperation.UPDATE_FILE:
                    if old is None or sha256_bytes(old) != change.expected_old_fingerprint:
                        raise WorkspaceExecutionError("Stale file precondition")
                    filesystem.write_bytes(path, contents[path])
                elif change.operation is WorkspaceOperation.DELETE_FILE:
                    if old is None or sha256_bytes(old) != change.expected_old_fingerprint:
                        raise WorkspaceExecutionError("Stale delete precondition")
                    filesystem.delete_file(path)
                changed.append(path)
            if command.policy.create_local_commit:
                git.commit(changed, command.policy.commit_message or "")
                git_mutated = True
            after_repo = git.inspect()
            after = filesystem.inspect(command.target, after_repo)
            evidence = tuple(
                FileEvidence(
                    path,
                    sha256_bytes(filesystem.read_bytes(path)),
                    len(filesystem.read_bytes(path)),
                )
                for path in sorted(set(changed))
                if filesystem.exists(path)
            )
            return self._receipt(
                command,
                before,
                after,
                before_repo,
                after_repo,
                evidence,
                ExecutionOutcome.APPLIED,
                ReconciliationStatus.CLEAN,
            )
        except Exception:
            rollback_ok = not git_mutated
            for path, original in reversed(tuple(originals.items())):
                try:
                    if original is None and filesystem.exists(path):
                        filesystem.delete_file(path)
                    elif original is not None:
                        filesystem.write_bytes(path, original)
                except OSError:
                    rollback_ok = False
            for path in reversed(created_directories):
                try:
                    filesystem.remove_directory(path)
                except OSError:
                    rollback_ok = False
            after_repo = git.inspect()
            after = filesystem.inspect(command.target, after_repo)
            return self._receipt(
                command,
                before,
                after,
                before_repo,
                after_repo,
                (),
                ExecutionOutcome.FAILED_ROLLED_BACK
                if rollback_ok
                else ExecutionOutcome.RECONCILIATION_REQUIRED,
                ReconciliationStatus.CLEAN if rollback_ok else ReconciliationStatus.REQUIRED,
            )

    @staticmethod
    def _receipt(
        command: ApplyWorkspaceCommand,
        before: object,
        after: object,
        before_repo: object,
        after_repo: object,
        evidence: tuple[FileEvidence, ...],
        outcome: ExecutionOutcome,
        reconciliation: ReconciliationStatus,
    ) -> WorkspaceExecutionReceipt:
        from arch_web.domain.workspace import RepositoryBaseline, WorkspaceBaseline

        assert isinstance(before, WorkspaceBaseline)
        assert isinstance(after, WorkspaceBaseline)
        assert isinstance(before_repo, RepositoryBaseline)
        assert isinstance(after_repo, RepositoryBaseline)
        repository = RepositoryEvidence(
            before_repo.head,
            after_repo.head,
            after_repo.branch,
            tuple(item.path for item in evidence),
            not after_repo.dirty_paths,
        )
        return WorkspaceExecutionReceipt(
            CURRENT_WEB_CONTRACT_VERSION,
            command.execution_id,
            command.target.project_id,
            command.target.workspace_id,
            command.prepared.change_set.canonical_fingerprint(),
            command.prepared.plan.canonical_fingerprint(),
            command.prepared.stack.canonical_fingerprint(),
            before.canonical_fingerprint(),
            after.tree_fingerprint,
            repository,
            evidence,
            outcome,
            reconciliation,
        )


__all__ = ("WorkspaceExecutor", "dry_run_workspace")
