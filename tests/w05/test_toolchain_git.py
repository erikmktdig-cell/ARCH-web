"""Toolchain allowlisting, redaction, Git inspection, and locking."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from arch_web.adapters.local.git import GitAdapterError, LocalGit
from arch_web.adapters.local.lock import LocalWorkspaceLocks, WorkspaceLockedError
from arch_web.adapters.local.toolchain import LocalToolchainProbe, ToolProbeSpec, redact_output


def test_toolchain_probe_uses_typed_argv_and_reports_missing(tmp_path: Path) -> None:
    available = LocalToolchainProbe(tmp_path).probe(ToolProbeSpec("git", "git"))
    missing = LocalToolchainProbe(tmp_path).probe(ToolProbeSpec("missing", "definitely-not-a-tool"))
    assert available.available
    assert available.version
    assert not missing.available
    assert missing.version is None
    assert available.output_digest.startswith("sha256:")


def test_diagnostics_are_bounded_and_redacted() -> None:
    value = "token=super-secret\n" + "x" * 3000
    redacted = redact_output(value)
    assert "super-secret" not in redacted
    assert "[REDACTED]" in redacted
    assert len(redacted) <= 2010


def test_git_inspection_new_branch_dirty_and_detached(tmp_path: Path) -> None:
    git = LocalGit(tmp_path)
    assert not git.inspect().present
    git.initialize()
    subprocess.run(
        ["git", "config", "user.email", "test@example.invalid"], cwd=tmp_path, check=True
    )
    subprocess.run(["git", "config", "user.name", "ARCH Test"], cwd=tmp_path, check=True)
    (tmp_path / "tracked.txt").write_text("one", encoding="utf-8")
    head = git.commit(("tracked.txt",), "initial")
    clean = git.inspect()
    assert clean.head == head
    assert clean.branch
    assert not clean.dirty_paths
    (tmp_path / "tracked.txt").write_text("two", encoding="utf-8")
    assert git.inspect().dirty_paths == ("tracked.txt",)
    subprocess.run(
        ["git", "checkout", "--detach", head], cwd=tmp_path, check=True, capture_output=True
    )
    assert git.inspect().detached


def test_git_commit_requires_explicit_paths(tmp_path: Path) -> None:
    git = LocalGit(tmp_path)
    git.initialize()
    with pytest.raises(GitAdapterError, match="approved"):
        git.commit((), "nothing")


def test_workspace_lock_rejects_concurrent_owner(tmp_path: Path) -> None:
    locks = LocalWorkspaceLocks()
    with (
        locks.acquire(tmp_path, "one"),
        pytest.raises(WorkspaceLockedError),
        locks.acquire(tmp_path, "two"),
    ):
        pass
