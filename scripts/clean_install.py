"""Install release artifacts with released dependency tags in a fresh environment."""

from __future__ import annotations

import argparse
import subprocess
import tempfile
import venv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
KERNEL_SOURCE = "arch-kernel @ git+https://github.com/erikmktdig-cell/ARCH-kernel.git@v0.1.0"
RUNTIME_SOURCE = "arch-runtime @ git+https://github.com/erikmktdig-cell/ARCH-runtime.git@v0.1.0"


def _python(environment: Path) -> Path:
    windows = environment / "Scripts" / "python.exe"
    return windows if windows.exists() else environment / "bin" / "python"


def _run(command: list[str], cwd: Path) -> None:
    subprocess.run(command, cwd=cwd, check=True)


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
        environment = root / "venv"
        venv.EnvBuilder(with_pip=True, clear=True).create(environment)
        python = _python(environment)
        _run([str(python), "-m", "pip", "install", KERNEL_SOURCE], root)
        _run([str(python), "-m", "pip", "install", "--no-deps", RUNTIME_SOURCE], root)
        _run([str(python), "-m", "pip", "install", "--no-deps", str(artifact)], root)
        _run(
            [
                str(python),
                "-I",
                str(ROOT / "scripts" / "installed_smoke.py"),
                str(root / "runtime.db"),
            ],
            root,
        )
    print(f"PASS: isolated install and integration smoke for {artifact.name}")


if __name__ == "__main__":
    main()
