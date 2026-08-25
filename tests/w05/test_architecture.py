"""W05 executable dependency and scope boundaries."""

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
def test_subprocess_is_confined_to_git_and_toolchain_adapters() -> None:
    users = {
        path.relative_to(SOURCE).as_posix()
        for path in SOURCE.rglob("*.py")
        if "subprocess" in _imports(path)
    }
    assert users == {
        "adapters/local/git.py",
        "adapters/local/toolchain.py",
        "adapters/qa/chromium.py",
    }


@pytest.mark.architecture
def test_w05_domain_and_planning_do_not_mutate_or_probe() -> None:
    paths = [
        SOURCE / "domain" / "workspace.py",
        SOURCE / "application" / "workspace" / "planning.py",
    ]
    forbidden = {"os", "pathlib", "subprocess", "shutil", "socket", "sqlite3"}
    for path in paths:
        assert {item.split(".", 1)[0] for item in _imports(path)}.isdisjoint(forbidden)


@pytest.mark.architecture
def test_no_remote_deployment_browser_or_product_framework_dependencies() -> None:
    paths = [
        path
        for path in SOURCE.rglob("*.py")
        if "adapters/backend" not in path.relative_to(SOURCE).as_posix()
    ]
    imports = {item for path in paths for item in _imports(path)}
    forbidden = {
        "github",
        "gitlab",
        "boto3",
        "playwright",
        "selenium",
        "react",
        "next",
        "vite",
    }
    assert {item.split(".", 1)[0] for item in imports}.isdisjoint(forbidden)
    sqlite_users = {
        path.relative_to(SOURCE).as_posix()
        for path in SOURCE.rglob("*.py")
        if "sqlite3" in _imports(path)
    }
    assert sqlite_users == {
        "adapters/backend/sqlite.py",
        "adapters/qa/integration.py",
    }
    assert not any(item.startswith("arch_runtime.") for item in imports)
