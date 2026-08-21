"""Process-local exclusive workspace lock adapter."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from threading import Lock, RLock
from typing import ClassVar


class WorkspaceLockedError(RuntimeError):
    pass


class LocalWorkspaceLocks:
    _guard: ClassVar[RLock] = RLock()
    _locks: ClassVar[dict[str, Lock]] = {}

    @contextmanager
    def acquire(self, root: Path, execution_id: str) -> Iterator[None]:
        key = str(root.resolve(strict=False)).casefold()
        with self._guard:
            lock = self._locks.setdefault(key, Lock())
        if not lock.acquire(blocking=False):
            raise WorkspaceLockedError(f"Workspace is already locked for {execution_id}")
        try:
            yield
        finally:
            lock.release()


__all__ = ("LocalWorkspaceLocks", "WorkspaceLockedError")
