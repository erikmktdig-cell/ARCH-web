"""W07 executable architecture boundaries."""

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
def test_backend_core_is_framework_and_effect_free() -> None:
    paths = [
        SOURCE / "domain" / "backend.py",
        *(SOURCE / "application" / "backend").glob("*.py"),
        SOURCE / "ports" / "backend.py",
    ]
    forbidden = {
        "anthropic",
        "django",
        "fastapi",
        "flask",
        "httpx",
        "openai",
        "os",
        "pathlib",
        "requests",
        "socket",
        "sqlite3",
        "subprocess",
    }
    imports = {item.split(".", 1)[0] for path in paths for item in _imports(path)}
    assert imports.isdisjoint(forbidden)


@pytest.mark.architecture
def test_application_database_access_is_bounded_and_runtime_private_api_absent() -> None:
    sqlite_users = {
        path.relative_to(SOURCE).as_posix()
        for path in SOURCE.rglob("*.py")
        if "sqlite3" in _imports(path)
    }
    assert sqlite_users == {"adapters/backend/sqlite.py"}
    imports = {item for path in SOURCE.rglob("*.py") for item in _imports(path)}
    assert not any(item.startswith("arch_runtime.") for item in imports)


@pytest.mark.architecture
def test_w07_contains_no_delivery_or_qa_scope() -> None:
    names = {path.stem for path in SOURCE.rglob("*.py")}
    assert names.isdisjoint({"browser_qa", "deployment", "preview", "release", "server"})


@pytest.mark.architecture
def test_backend_tests_do_not_import_public_network_clients() -> None:
    forbidden = {"httpx", "requests", "socket", "urllib"}
    imports = {
        item.split(".", 1)[0]
        for path in (ROOT / "tests" / "w07").glob("*.py")
        for item in _imports(path)
    }
    assert imports.isdisjoint(forbidden)
