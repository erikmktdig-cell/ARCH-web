"""Release evidence rejects stale metadata, weak coverage and altered dependencies."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tomllib
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parents[2]))

from scripts.clean_install import RELEASED_WHEELS, verify_digest
from scripts.release_tools import ReleaseCheckError, _validate_members

pytestmark = pytest.mark.release
ROOT = Path(__file__).parents[2]


def test_dependency_lock_records_exact_published_digests() -> None:
    lock = tomllib.loads((ROOT / "uv.lock").read_text(encoding="utf-8"))
    packages = {item["name"]: item for item in lock["package"]}
    for name, (url, digest) in RELEASED_WHEELS.items():
        assert packages[name]["version"] == "0.2.0"
        assert packages[name]["source"] == {"url": url}
        assert packages[name]["wheels"][0]["hash"] == f"sha256:{digest}"


def test_digest_verification_precedes_dependency_install(tmp_path: Path) -> None:
    wheel = tmp_path / "dependency.whl"
    wheel.write_bytes(b"verified release")
    digest = hashlib.sha256(wheel.read_bytes()).hexdigest()
    verify_digest(wheel, digest)
    wheel.write_bytes(b"altered release")
    with pytest.raises(RuntimeError, match="digest mismatch"):
        verify_digest(wheel, digest)


@pytest.mark.parametrize(
    ("branches", "covered", "success"),
    [(100, 89, False), (100, 90, True), (0, 0, False), (10, 11, False)],
)
def test_branch_gate_does_not_accept_combined_coverage(
    tmp_path: Path, branches: int, covered: int, success: bool
) -> None:
    report = tmp_path / "coverage.json"
    report.write_text(
        json.dumps(
            {
                "totals": {
                    "num_branches": branches,
                    "covered_branches": covered,
                    "percent_covered": 100,
                }
            }
        ),
        encoding="utf-8",
    )
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts/check_branch_coverage.py"), str(report)],
        capture_output=True,
        check=False,
    )
    assert (result.returncode == 0) is success


@pytest.mark.parametrize(
    ("name", "data"),
    [
        ("../escape", b""),
        ("/absolute", b""),
        ("nested\\escape", b""),
        (".env", b""),
        ("state.sqlite", b""),
        (".coverage", b""),
        ("package/METADATA", b"Requires-Dist: dependency @ file:" + b"//checkout"),
        ("package/PKG-INFO", b"Requires-Dist: dependency @ git+https://example.invalid/repo"),
    ],
)
def test_archive_rejects_unsafe_or_nonportable_members(name: str, data: bytes) -> None:
    with pytest.raises(ReleaseCheckError):
        _validate_members(Path("candidate.whl"), [(name, data)])
