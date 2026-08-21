"""Allowlisted, read-only local toolchain probing."""

from __future__ import annotations

import hashlib
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

from arch_web.domain.workspace import ToolchainCapability

_SECRET = re.compile(r"(?i)(token|password|secret|api[_-]?key)\s*[:=]\s*\S+")


def redact_output(value: str, *, limit: int = 2000) -> str:
    return _SECRET.sub(r"\1=[REDACTED]", value[:limit])


@dataclass(frozen=True, slots=True)
class ToolProbeSpec:
    tool_id: str
    executable: str
    version_args: tuple[str, ...] = ("--version",)


class LocalToolchainProbe:
    def __init__(self, cwd: Path, *, timeout: float = 5.0) -> None:
        self.cwd = cwd
        self.timeout = timeout

    def probe(self, spec: ToolProbeSpec) -> ToolchainCapability:
        try:
            result = subprocess.run(
                [spec.executable, *spec.version_args],
                cwd=self.cwd,
                shell=False,
                check=False,
                timeout=self.timeout,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                env={"PATH": os_path()},
            )
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return ToolchainCapability(
                spec.tool_id, spec.executable, False, None, "sha256:" + "0" * 64
            )
        output = redact_output((result.stdout or result.stderr).strip())
        digest = "sha256:" + hashlib.sha256(output.encode()).hexdigest()
        first_line = output.splitlines()[0] if output else "unknown"
        return ToolchainCapability(
            spec.tool_id, spec.executable, result.returncode == 0, first_line, digest
        )


def os_path() -> str:
    import os

    return os.environ.get("PATH", "")


__all__ = ("LocalToolchainProbe", "ToolProbeSpec", "redact_output")
