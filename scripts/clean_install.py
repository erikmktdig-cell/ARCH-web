"""Verify released wheels and execute the lifecycle outside all checkouts."""

from __future__ import annotations

import argparse
import hashlib
import os
import shutil
import subprocess
import sys
import tempfile
import tomllib
import urllib.request
import venv
from importlib.metadata import version
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RELEASED_WHEELS = {
    "arch-kernel": (
        "https://github.com/erikmktdig-cell/ARCH-kernel/releases/download/v0.2.0/arch_kernel-0.2.0-py3-none-any.whl",
        "3c581c37c4890ac50ff8c1722aca7cc4e29fed85a37656d6f08e22ffb8847b5c",
    ),
    "arch-runtime": (
        "https://github.com/erikmktdig-cell/ARCH-runtime/releases/download/v0.2.0/arch_runtime-0.2.0-py3-none-any.whl",
        "6f0271bb1dca67dfd8aaf6b4b5a6a43bd3b2e8e2ab110b01e99aa48c719a42f2",
    ),
}


def verify_digest(path: Path, expected: str) -> None:
    if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
        raise RuntimeError(f"released dependency digest mismatch: {path.name}")


def _python(environment: Path) -> Path:
    windows = environment / "Scripts" / "python.exe"
    return windows if windows.exists() else environment / "bin" / "python"


def _run(command: list[str], cwd: Path) -> None:
    environment = dict(os.environ)
    for key in ("PYTHONPATH", "PYTHONHOME", "VIRTUAL_ENV"):
        environment.pop(key, None)
    subprocess.run(command, cwd=cwd, env=environment, check=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("artifact", type=Path)
    args = parser.parse_args()
    artifact = args.artifact.resolve()
    if artifact.is_dir():
        candidates = sorted(
            path
            for path in artifact.iterdir()
            if path.suffix == ".whl" or path.name.endswith(".tar.gz")
        )
        if len(candidates) != 1:
            raise RuntimeError("artifact directory must contain exactly one wheel or sdist")
        artifact = candidates[0]
    if not artifact.is_file():
        raise FileNotFoundError(artifact)

    with tempfile.TemporaryDirectory(prefix="arch-web-install-") as temp_name:
        root = Path(temp_name)
        artifacts = []
        for url, digest in RELEASED_WHEELS.values():
            destination = root / url.rsplit("/", 1)[1]
            with urllib.request.urlopen(url, timeout=120) as response:
                destination.write_bytes(response.read())
            verify_digest(destination, digest)
            artifacts.append(str(destination))
        candidate = root / artifact.name
        shutil.copy2(artifact, candidate)
        shutil.copy2(ROOT / "scripts" / "installed_smoke.py", root / "installed_smoke.py")
        # Copy fixture support only, never package source or checkout import paths.
        shutil.copytree(
            ROOT / "tests",
            root / "tests",
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
        )
        environment = root / "venv"
        venv.EnvBuilder(with_pip=True).create(environment)
        python = _python(environment)
        lock = tomllib.loads((ROOT / "uv.lock").read_text(encoding="utf-8"))
        constraints = root / "constraints.txt"
        constraints.write_text(
            "\n".join(
                sorted(
                    {
                        f"{item['name']}=={item['version']}"
                        for item in lock["package"]
                        if "registry" in item["source"]
                    }
                )
            )
            + "\n",
            encoding="utf-8",
        )
        _run(
            [
                str(python),
                "-m",
                "pip",
                "install",
                "--constraint",
                str(constraints),
                *artifacts,
                str(candidate),
                f"pytest=={version('pytest')}",
                f"hypothesis=={version('hypothesis')}",
            ],
            root,
        )
        _run([str(python), "-I", str(root / "installed_smoke.py")], root)
    print(f"PASS: isolated full lifecycle for {artifact.name}; host Python {sys.version}")


if __name__ == "__main__":
    main()
