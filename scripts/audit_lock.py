"""Audit every locked registry version, including other-platform dependencies."""

from __future__ import annotations

import subprocess
import sys
import tempfile
import tomllib
from pathlib import Path


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    lock = tomllib.loads((root / "uv.lock").read_text(encoding="utf-8"))
    packages = sorted(
        {
            f"{item['name']}=={item['version']}"
            for item in lock["package"]
            if "registry" in item["source"]
        }
    )
    with tempfile.TemporaryDirectory(prefix="arch-web-audit-") as directory:
        requirements = Path(directory) / "requirements.txt"
        requirements.write_text("\n".join(packages) + "\n", encoding="utf-8")
        subprocess.run(
            [
                sys.executable,
                "-m",
                "pip_audit",
                "-r",
                str(requirements),
                "--no-deps",
                "--disable-pip",
                "--progress-spinner",
                "off",
            ],
            check=True,
        )
    print(f"PASS: all {len(packages)} locked registry versions audited")


if __name__ == "__main__":
    main()
