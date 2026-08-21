"""Narrow, local-only Git CLI adapter."""

from __future__ import annotations

import subprocess
from collections.abc import Iterable, Sequence
from pathlib import Path

from arch_web.domain.workspace import RepositoryBaseline


class GitAdapterError(RuntimeError):
    pass


class LocalGit:
    def __init__(self, root: Path, *, timeout: float = 10.0) -> None:
        self.root = root
        self.timeout = timeout

    def _run(self, argv: Sequence[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
        result = subprocess.run(
            ["git", *argv],
            cwd=self.root,
            shell=False,
            check=False,
            timeout=self.timeout,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        if check and result.returncode != 0:
            raise GitAdapterError((result.stderr or result.stdout)[:1000])
        return result

    def inspect(self) -> RepositoryBaseline:
        present = (self.root / ".git").is_dir()
        if not present:
            return RepositoryBaseline(False, None, None, False)
        head_result = self._run(("rev-parse", "--verify", "HEAD"), check=False)
        head = head_result.stdout.strip() if head_result.returncode == 0 else None
        branch_result = self._run(("symbolic-ref", "--quiet", "--short", "HEAD"), check=False)
        branch = branch_result.stdout.strip() if branch_result.returncode == 0 else None
        status = self._run(("status", "--porcelain=v1", "-z")).stdout
        dirty = tuple(sorted(entry[3:] for entry in status.split("\x00") if entry))
        remote_output = self._run(("remote",), check=False).stdout
        remotes = tuple(sorted(item for item in remote_output.splitlines() if item))
        return RepositoryBaseline(
            True, head, branch, branch is None and head is not None, dirty, remotes
        )

    def initialize(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        self._run(("init",))

    def commit(self, paths: Iterable[str], message: str) -> str:
        approved = tuple(sorted(paths))
        if not approved:
            raise GitAdapterError("No approved paths to commit")
        self._run(("add", "--", *approved))
        self._run(("commit", "-m", message, "--", *approved))
        return self._run(("rev-parse", "HEAD")).stdout.strip()


__all__ = ("GitAdapterError", "LocalGit")
