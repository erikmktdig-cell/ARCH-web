"""W02-specific layer and scope boundaries."""

import ast
import subprocess
import sys
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
def test_requirements_domain_and_application_are_io_and_framework_free() -> None:
    forbidden = {
        "anthropic",
        "django",
        "fastapi",
        "httpx",
        "openai",
        "pathlib",
        "requests",
        "socket",
        "sqlite3",
        "subprocess",
    }
    paths = list((SOURCE / "domain").glob("*.py")) + list(
        (SOURCE / "application" / "requirements").glob("*.py")
    )
    violations = [
        f"{path.name}:{name}"
        for path in paths
        for name in _imports(path)
        if name.split(".", 1)[0] in forbidden
    ]
    assert violations == []


@pytest.mark.architecture
def test_only_runtime_bridge_depends_on_public_arch_runtime() -> None:
    runtime_importers = {
        path.relative_to(SOURCE).as_posix()
        for path in SOURCE.rglob("*.py")
        if any(name == "arch_runtime" for name in _imports(path))
    }
    assert runtime_importers == {
        "application/architecture/models.py",
        "application/requirements/models.py",
        "runtime_bridge/architecture.py",
        "runtime_bridge/requirements.py",
    }
    assert not any(
        name.startswith("arch_runtime.") for path in SOURCE.rglob("*.py") for name in _imports(path)
    )


@pytest.mark.architecture
def test_no_w03_or_later_feature_modules_exist() -> None:
    forbidden = {
        "agents",
        "deployment",
        "design_system",
        "frontend_generator",
        "github_adapter",
        "ia_generator",
        "node_runner",
        "preview",
        "repository_workspace",
    }
    assert {path.stem for path in SOURCE.rglob("*.py")}.isdisjoint(forbidden)


@pytest.mark.architecture
def test_clean_process_can_import_public_package() -> None:
    result = subprocess.run(
        [sys.executable, "-c", "import arch_web; print(arch_web.__version__)"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "0.1.0"
