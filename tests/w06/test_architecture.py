"""W06 executable architecture boundaries."""

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
def test_frontend_domain_and_application_have_no_external_effect_engines() -> None:
    paths = [
        SOURCE / "domain" / "frontend.py",
        *(SOURCE / "application" / "frontend").glob("*.py"),
    ]
    forbidden = {
        "os",
        "pathlib",
        "shutil",
        "socket",
        "sqlite3",
        "subprocess",
        "requests",
        "httpx",
    }
    for path in paths:
        assert {name.split(".", 1)[0] for name in _imports(path)}.isdisjoint(forbidden)


@pytest.mark.architecture
def test_frontend_core_has_no_llm_or_framework_dependency() -> None:
    paths = [
        SOURCE / "domain" / "frontend.py",
        *(SOURCE / "application" / "frontend").glob("*.py"),
        SOURCE / "ports" / "frontend.py",
    ]
    forbidden = {
        "anthropic",
        "openai",
        "langchain",
        "crewai",
        "react",
        "next",
        "vite",
        "django",
        "fastapi",
        "playwright",
        "selenium",
    }
    imports = {name.split(".", 1)[0] for path in paths for name in _imports(path)}
    assert imports.isdisjoint(forbidden)


@pytest.mark.architecture
def test_runtime_bridge_uses_only_public_runtime_and_no_storage() -> None:
    path = SOURCE / "runtime_bridge" / "frontend.py"
    imports = _imports(path)
    assert "arch_runtime" in imports
    assert not any(name.startswith("arch_runtime.") for name in imports)
    assert {name.split(".", 1)[0] for name in imports}.isdisjoint(
        {"sqlite3", "pathlib", "subprocess"}
    )


@pytest.mark.architecture
def test_no_w08_delivery_or_remote_modules_exist() -> None:
    forbidden = {
        "browser_qa",
        "deployment",
        "github",
        "preview",
        "release",
        "server",
    }
    paths = [
        SOURCE / "domain" / "frontend.py",
        *(SOURCE / "application" / "frontend").glob("*.py"),
        *(SOURCE / "adapters" / "frontend").glob("*.py"),
    ]
    assert {path.stem for path in paths}.isdisjoint(forbidden)


@pytest.mark.architecture
def test_w06_does_not_duplicate_workspace_adapters() -> None:
    frontend_files = list((SOURCE / "adapters" / "frontend").glob("*.py"))
    imports = {name for path in frontend_files for name in _imports(path)}
    assert "subprocess" not in imports
    assert "pathlib" not in imports
    assert not any("adapters.local" in name for name in imports)
