"""W03 scope and dependency boundaries."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

SOURCE = Path(__file__).parents[2] / "src" / "arch_web"


@pytest.mark.architecture
def test_w03_contains_no_framework_or_execution_dependencies() -> None:
    forbidden = {"react", "next", "vite", "node", "subprocess", "sqlite3", "requests", "httpx"}
    imports: set[str] = set()
    for path in SOURCE.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imports.add(node.module.split(".")[0])
    assert not imports & forbidden


@pytest.mark.architecture
def test_w03_does_not_create_design_or_generation_modules() -> None:
    paths = {path.relative_to(SOURCE).as_posix() for path in SOURCE.rglob("*.py")}
    assert not any("design" in path or "generation" in path or "frontend" in path for path in paths)
