"""W04 framework, execution, and future-scope boundaries."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

SOURCE = Path(__file__).parents[2] / "src" / "arch_web"


def _w04_paths() -> tuple[Path, ...]:
    paths = list((SOURCE / "application" / "design").rglob("*.py"))
    paths.extend((SOURCE / "domain").glob("design_*.py"))
    paths.extend((SOURCE / "domain").glob("ui_*.py"))
    paths.append(SOURCE / "runtime_bridge" / "ui.py")
    return tuple(paths)


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    values: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            values.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            values.add(node.module)
    return values


@pytest.mark.architecture
def test_w04_has_no_framework_tooling_or_infrastructure_dependencies() -> None:
    forbidden = {
        "react",
        "next",
        "vite",
        "tailwind",
        "node",
        "subprocess",
        "sqlite3",
        "requests",
        "httpx",
        "playwright",
        "selenium",
        "figma",
        "git",
    }
    roots = {name.split(".")[0] for path in _w04_paths() for name in _imports(path)}
    assert not roots & forbidden


@pytest.mark.architecture
def test_w04_contains_no_css_frontend_or_w05_generation_modules() -> None:
    paths = {path.relative_to(SOURCE).as_posix().lower() for path in _w04_paths()}
    forbidden_fragments = ("css", "tailwind", "frontend", "generation", "workspace")
    assert not any(fragment in path for fragment in forbidden_fragments for path in paths)


@pytest.mark.architecture
def test_runtime_bridge_uses_only_public_runtime_root() -> None:
    ui_bridge = SOURCE / "runtime_bridge" / "ui.py"
    imports = _imports(ui_bridge)
    assert "arch_runtime" in imports
    assert not any(name.startswith("arch_runtime.") for name in imports)
