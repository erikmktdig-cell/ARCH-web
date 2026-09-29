from __future__ import annotations

import os
import subprocess
import sys
import tarfile
import zipfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parents[2]))

from scripts.release_tools import inspect_artifacts

pytestmark = pytest.mark.release
ROOT = Path(__file__).parents[2]


def _build(output: Path) -> tuple[Path, Path]:
    environment = {**os.environ, "SOURCE_DATE_EPOCH": "1787702400", "PYTHONHASHSEED": "0"}
    subprocess.run(
        [sys.executable, "-m", "build", "--outdir", str(output)],
        cwd=ROOT,
        env=environment,
        check=True,
        capture_output=True,
        text=True,
    )
    return next(output.glob("*.whl")), next(output.glob("*.tar.gz"))


def test_wheel_and_sdist_contain_only_intended_release_files(tmp_path: Path) -> None:
    wheel, sdist = _build(tmp_path / "dist")
    inventory = inspect_artifacts(tmp_path / "dist")
    assert len(inventory) == 2

    with zipfile.ZipFile(wheel) as archive:
        wheel_names = set(archive.namelist())
        metadata_name = next(name for name in wheel_names if name.endswith(".dist-info/METADATA"))
        metadata = archive.read(metadata_name).decode("utf-8")
    assert "arch_web/py.typed" in wheel_names
    assert not any(name.startswith(("tests/", "src/")) for name in wheel_names)
    assert "Requires-Python: <3.14,>=3.12" in metadata
    assert "Requires-Dist: arch-runtime<0.3.0,>=0.2.0" in metadata

    with tarfile.open(sdist, mode="r:gz") as archive:
        sdist_names = {Path(name).as_posix() for name in archive.getnames()}
    assert any(name.endswith("/src/arch_web/py.typed") for name in sdist_names)
    assert any(name.endswith("/SECURITY.md") for name in sdist_names)
    assert not any("tests" in Path(name).parts for name in sdist_names)
