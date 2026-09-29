from __future__ import annotations

import io
import subprocess
import sys
import tarfile
import zipfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parents[2]))

from scripts.release_tools import (
    BASELINE_COMMIT,
    ReleaseCheckError,
    audit_tracked_source,
    inspect_artifacts,
    release_manifest,
)

pytestmark = pytest.mark.release


def test_release_manifest_records_exact_external_evidence() -> None:
    manifest = release_manifest(
        final_commit="a" * 40,
        tests=560,
        skips=1,
        branch_coverage=94.2,
        artifacts=[{"filename": "arch_web.whl", "sha256": "b" * 64}],
        clean_install={"windows-3.12-wheel": "pass"},
        hosted_ci={"run": "pending"},
        security_audit="pass",
        governance={"branch_protection": "pending"},
        quality_gates={"pytest": "pending"},
    )
    assert manifest["baseline_commit"] == BASELINE_COMMIT
    assert manifest["final_release_commit"] == "a" * 40
    assert manifest["artifact_sha256"] == {"arch_web.whl": "b" * 64}
    assert manifest["arch_runtime_resolved_version"] == "0.2.0"
    assert manifest["arch_kernel_resolved_version"] == "0.2.0"
    assert manifest["quality_gates"] == {"pytest": "pending"}


def test_tracked_source_audit_accepts_release_checkout() -> None:
    audit_tracked_source()


def test_artifact_inspection_rejects_test_leakage(tmp_path: Path) -> None:
    wheel = tmp_path / "arch_web-0.2.0-py3-none-any.whl"
    with zipfile.ZipFile(wheel, "w") as archive:
        archive.writestr("arch_web/py.typed", "")
        archive.writestr("tests/test_leak.py", "")
    sdist = tmp_path / "arch_web-0.2.0.tar.gz"
    with tarfile.open(sdist, "w:gz") as archive:
        for name in (
            "arch_web-0.2.0/src/arch_web/py.typed",
            "arch_web-0.2.0/SECURITY.md",
        ):
            info = tarfile.TarInfo(name)
            info.size = 0
            archive.addfile(info, io.BytesIO())
    with pytest.raises(ReleaseCheckError, match="forbidden archive member"):
        inspect_artifacts(tmp_path)


def test_release_scripts_load_when_executed_by_path() -> None:
    root = Path(__file__).parents[2]
    for script in (
        "scripts/check_reproducible_build.py",
        "scripts/build_release_manifest.py",
        "scripts/check_release.py",
    ):
        subprocess.run(
            [sys.executable, "-I", "-c", f"import runpy; runpy.run_path({script!r})"],
            cwd=root,
            check=True,
            capture_output=True,
            text=True,
        )


def test_release_scripts_do_not_embed_personal_paths() -> None:
    root = Path(__file__).parents[2]
    for path in (root / "scripts").glob("*.py"):
        assert "C:" + "\\Users\\" not in path.read_text(encoding="utf-8")
