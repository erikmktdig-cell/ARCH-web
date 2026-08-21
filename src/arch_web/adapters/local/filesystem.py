"""Confined local filesystem inspection and mutation."""

from __future__ import annotations

import hashlib
import os
import tempfile
from pathlib import Path

from arch_web.contracts.canonical import canonical_bytes
from arch_web.domain.workspace import (
    FileEvidence,
    RepositoryBaseline,
    ToolchainCapability,
    WorkspaceBaseline,
    WorkspaceTarget,
)
from arch_web.workspace_paths import confined_path, normalize_managed_path

_EXCLUDED = {
    ".git",
    ".arch-web",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".uv-cache",
    "node_modules",
    "dist",
    "build",
    "__pycache__",
}


def sha256_bytes(content: bytes) -> str:
    return "sha256:" + hashlib.sha256(content).hexdigest()


class LocalFileSystem:
    def __init__(self, root: Path, capabilities: tuple[ToolchainCapability, ...] = ()) -> None:
        self.root = root
        self.capabilities = capabilities

    def _path(self, relative: str) -> Path:
        return confined_path(self.root, relative)

    def exists(self, path: str) -> bool:
        return self._path(path).exists()

    def read_bytes(self, path: str) -> bytes:
        return self._path(path).read_bytes()

    def create_directory(self, path: str) -> None:
        self._path(path).mkdir(parents=True, exist_ok=True)

    def write_bytes(self, path: str, content: bytes) -> None:
        target = self._path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary = tempfile.mkstemp(prefix=".arch-write-", dir=target.parent)
        try:
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(content)
                stream.flush()
                os.fsync(stream.fileno())
            Path(temporary).replace(target)
        finally:
            temporary_path = Path(temporary)
            if temporary_path.exists():
                temporary_path.unlink()

    def delete_file(self, path: str) -> None:
        self._path(path).unlink()

    def remove_directory(self, path: str) -> None:
        self._path(path).rmdir()

    def inspect(self, target: WorkspaceTarget, repository: RepositoryBaseline) -> WorkspaceBaseline:
        files: list[FileEvidence] = []
        if self.root.exists():
            for item in self.root.rglob("*"):
                relative = item.relative_to(self.root)
                if any(part.casefold() in _EXCLUDED for part in relative.parts):
                    continue
                if item.is_symlink():
                    continue
                if item.is_file():
                    path = normalize_managed_path(relative.as_posix())
                    content = item.read_bytes()
                    files.append(FileEvidence(path, sha256_bytes(content), len(content)))
        ordered = tuple(sorted(files, key=lambda entry: entry.path.casefold()))
        tree = sha256_bytes(
            canonical_bytes(tuple((item.path, item.fingerprint, item.size) for item in ordered))
        )
        return WorkspaceBaseline(
            target.workspace_id,
            target.project_id,
            self.root.exists(),
            ordered,
            tree,
            repository,
            self.capabilities,
        )


__all__ = ("LocalFileSystem", "sha256_bytes")
