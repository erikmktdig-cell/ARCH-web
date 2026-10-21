"""Fail-closed release artifact inspection and evidence generation."""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import tarfile
import zipfile
from collections.abc import Iterable
from email.parser import BytesParser
from pathlib import Path, PurePosixPath
from typing import Any

from packaging.requirements import Requirement

from arch_web import __version__

ROOT = Path(__file__).resolve().parents[1]
BASELINE_COMMIT = "cfa4e9a20780cc00354400f32170fe5fa0aa60c1"
VERSION = __version__
FORBIDDEN_PARTS = {
    ".git",
    ".hypothesis",
    ".mypy_cache",
    ".pytest-tmp",
    ".pytest_cache",
    ".ruff_cache",
    ".uv-cache",
    ".venv",
    "__pycache__",
    "browser-profiles",
    "dist",
    "htmlcov",
    "screenshots",
    "tests",
}
FORBIDDEN_SUFFIXES = (
    ".db",
    ".db-journal",
    ".db-shm",
    ".db-wal",
    ".sqlite",
    ".sqlite3",
)
SECRET_PATTERNS = (
    re.compile(r"github_pat_[A-Za-z0-9_]{20,}"),
    re.compile(r"ghp_[A-Za-z0-9]{20,}"),
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    re.compile(r"[A-Za-z]+://[^\s/:]+:[^\s/@]+@"),
)
UNIX_PERSONAL_PATH = re.compile(
    r"(?:^|[\s\"'=])/home/[A-Za-z0-9._-]+/(?:Documents|Desktop|Downloads|workspace|repos?|src)/",
    re.MULTILINE,
)


class ReleaseCheckError(RuntimeError):
    """Raised when release evidence fails closed."""


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _scan_text(name: str, data: bytes) -> None:
    try:
        content = data.decode("utf-8")
    except UnicodeDecodeError:
        return
    for pattern in SECRET_PATTERNS:
        if pattern.search(content):
            raise ReleaseCheckError(f"possible secret in {name}")
    if "C:" + "\\Users\\" in content or UNIX_PERSONAL_PATH.search(content):
        raise ReleaseCheckError(f"personal filesystem path in {name}")


def _wheel_members(path: Path) -> tuple[tuple[str, bytes], ...]:
    with zipfile.ZipFile(path) as archive:
        if any((item.external_attr >> 16) & 0o170000 == 0o120000 for item in archive.infolist()):
            raise ReleaseCheckError("symbolic link in wheel")
        return tuple((name, archive.read(name)) for name in archive.namelist())


def _sdist_members(path: Path) -> tuple[tuple[str, bytes], ...]:
    members: list[tuple[str, bytes]] = []
    with tarfile.open(path, mode="r:gz") as archive:
        for member in archive.getmembers():
            if member.issym() or member.islnk():
                raise ReleaseCheckError("link in sdist")
            if not member.isfile():
                members.append((member.name, b""))
                continue
            stream = archive.extractfile(member)
            if stream is None:
                raise ReleaseCheckError(f"cannot read archive member: {member.name}")
            members.append((member.name, stream.read()))
    return tuple(members)


def _validate_members(path: Path, members: Iterable[tuple[str, bytes]]) -> tuple[str, ...]:
    names: list[str] = []
    for name, data in members:
        names.append(name)
        if (
            PurePosixPath(name).is_absolute()
            or ".." in PurePosixPath(name).parts
            or "\\" in name
            or ":" in name
        ):
            raise ReleaseCheckError(f"unsafe archive path: {name}")
        parts = set(Path(name).parts)
        if parts.intersection(FORBIDDEN_PARTS) or name.endswith(FORBIDDEN_SUFFIXES):
            raise ReleaseCheckError(f"forbidden archive member: {name}")
        if Path(name).name.startswith(".env") or Path(name).name == ".coverage":
            raise ReleaseCheckError(f"forbidden environment or coverage file: {name}")
        _scan_text(f"{path.name}:{name}", data)
        if name.endswith(("METADATA", "PKG-INFO", "pyproject.toml")):
            content = data.decode("utf-8")
            if any(
                value in content for value in ("file:" + "//", "git+", "editable =", "../ARCH-")
            ):
                raise ReleaseCheckError("nonportable source dependency")
    return tuple(names)


def inspect_artifacts(directory: Path) -> list[dict[str, Any]]:
    artifacts = sorted(
        path
        for path in directory.iterdir()
        if path.suffix == ".whl" or path.name.endswith(".tar.gz")
    )
    expected = {f"arch_web-{VERSION}-py3-none-any.whl", f"arch_web-{VERSION}.tar.gz"}
    if {artifact.name for artifact in artifacts} != expected:
        raise ReleaseCheckError("release requires exactly one wheel and one sdist")
    inventory: list[dict[str, Any]] = []
    for artifact in artifacts:
        is_wheel = artifact.suffix == ".whl"
        members = _wheel_members(artifact) if is_wheel else _sdist_members(artifact)
        names = _validate_members(artifact, members)
        metadata = [
            data for name, data in members if name.endswith((".dist-info/METADATA", "/PKG-INFO"))
        ]
        if not metadata:
            raise ReleaseCheckError("missing distribution metadata")
        for raw in metadata:
            parsed = BytesParser().parsebytes(raw)
            if parsed["Name"] != "arch-web" or parsed["Version"] != VERSION:
                raise ReleaseCheckError("incorrect package identity")
            dependencies = [Requirement(value) for value in parsed.get_all("Requires-Dist", [])]
            if len(dependencies) != 1:
                raise ReleaseCheckError("unexpected dependencies")
            dependency = dependencies[0]
            if (
                dependency.name != "arch-runtime"
                or str(dependency.specifier) != "<0.3.0,>=0.2.0"
                or dependency.url is not None
                or dependency.marker is not None
                or dependency.extras
            ):
                raise ReleaseCheckError("incorrect Runtime dependency")
        if is_wheel and "arch_web/py.typed" not in names:
            raise ReleaseCheckError("wheel is missing arch_web/py.typed")
        if not is_wheel:
            if not any(name.endswith("/src/arch_web/py.typed") for name in names):
                raise ReleaseCheckError("sdist is missing typed package metadata")
            if not any(name.endswith("/SECURITY.md") for name in names):
                raise ReleaseCheckError("sdist is missing SECURITY.md")
        inventory.append(
            {
                "filename": artifact.name,
                "sha256": sha256(artifact),
                "size": artifact.stat().st_size,
                "members": len(names),
            }
        )
    return inventory


def tracked_files(root: Path = ROOT) -> tuple[Path, ...]:
    result = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=root,
        check=True,
        capture_output=True,
    )
    return tuple(root / item.decode() for item in result.stdout.split(b"\0") if item)


def audit_tracked_source(root: Path = ROOT) -> None:
    for path in tracked_files(root):
        relative = path.relative_to(root)
        if relative.name.startswith(".env") or path.name.endswith(FORBIDDEN_SUFFIXES):
            raise ReleaseCheckError(f"forbidden tracked file: {relative.as_posix()}")
        try:
            data = path.read_bytes()
        except OSError as error:
            raise ReleaseCheckError(f"cannot audit tracked file: {relative.as_posix()}") from error
        _scan_text(relative.as_posix(), data)


def release_manifest(
    *,
    final_commit: str,
    tests: int,
    skips: int,
    branch_coverage: float,
    artifacts: list[dict[str, Any]],
    clean_install: dict[str, str],
    hosted_ci: dict[str, str],
    security_audit: str,
    governance: dict[str, str],
    quality_gates: dict[str, str],
) -> dict[str, Any]:
    return {
        "schema": "arch-web-release-manifest/v1",
        "generated_by": "scripts/build_release_manifest.py",
        "package": "arch-web",
        "version": VERSION,
        "baseline_commit": BASELINE_COMMIT,
        "final_release_commit": final_commit,
        "python": ["3.12", "3.13"],
        "arch_runtime_dependency": "arch-runtime>=0.2.0,<0.3.0",
        "arch_runtime_resolved_version": "0.2.0",
        "arch_kernel_resolved_version": "0.2.0",
        "tests": tests,
        "skips": skips,
        "branch_coverage": branch_coverage,
        "quality_gates": quality_gates,
        "artifacts": [item["filename"] for item in artifacts],
        "artifact_sha256": {item["filename"]: item["sha256"] for item in artifacts},
        "clean_install": clean_install,
        "hosted_ci": hosted_ci,
        "security_audit": security_audit,
        "repository": "erikmktdig-cell/ARCH-web",
        "tag": f"v{VERSION}",
        "tag_peeled_commit": final_commit,
        "github_release": governance.get("github_release", "pending"),
        "governance": governance,
    }


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
