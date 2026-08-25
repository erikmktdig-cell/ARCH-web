"""W08 layer, execution-boundary, and scope architecture tests."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[2]
SOURCE = ROOT / "src" / "arch_web"


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    values: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            values.update(item.name for item in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            values.add(node.module)
    return values


@pytest.mark.architecture
def test_qa_core_has_no_browser_process_network_or_filesystem_capability() -> None:
    paths = [SOURCE / "domain" / "qa.py", *(SOURCE / "application" / "qa").glob("*.py")]
    forbidden = {
        "http.server",
        "os",
        "pathlib",
        "requests",
        "selenium",
        "shutil",
        "socket",
        "subprocess",
        "tempfile",
        "urllib",
    }
    violations = {
        f"{path.relative_to(SOURCE).as_posix()}:{name}"
        for path in paths
        for name in _imports(path)
        if name.split(".", 1)[0] in {item.split(".", 1)[0] for item in forbidden}
    }
    assert violations == set()


@pytest.mark.architecture
def test_browser_and_preview_capabilities_are_confined_to_qa_adapters() -> None:
    capability_roots = {"http", "socket", "subprocess", "tempfile", "urllib"}
    users = {
        path.relative_to(SOURCE).as_posix()
        for path in SOURCE.rglob("*.py")
        if {name.split(".", 1)[0] for name in _imports(path)} & capability_roots
    }
    assert users <= {
        "adapters/qa/chromium.py",
        "adapters/qa/local_preview.py",
        "adapters/local/filesystem.py",
        "adapters/local/git.py",
        "adapters/local/toolchain.py",
        "application/backend/execution.py",
        "application/frontend/execution.py",
    }


@pytest.mark.architecture
def test_w08_does_not_add_delivery_or_remediation_surfaces() -> None:
    forbidden = {"deployment", "remediation", "release", "server", "w09"}
    assert {path.stem for path in SOURCE.rglob("*.py")}.isdisjoint(forbidden)


@pytest.mark.architecture
def test_qa_runtime_bridge_uses_only_public_runtime_module() -> None:
    imports = _imports(SOURCE / "runtime_bridge" / "qa.py")
    assert "arch_runtime" in imports
    assert not any(item.startswith("arch_runtime.") for item in imports)
