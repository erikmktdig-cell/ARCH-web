"""W09 provider, Runtime, secret, and mutation-boundary guards."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

SOURCE = Path("src/arch_web")
CORE = (SOURCE / "domain" / "release.py", SOURCE / "application" / "release")


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
def test_neutral_release_core_has_no_provider_network_process_or_storage_sdk() -> None:
    paths = [CORE[0], *CORE[1].rglob("*.py")]
    forbidden = {
        "boto3",
        "docker",
        "google.cloud",
        "httpx",
        "kubernetes",
        "requests",
        "socket",
        "sqlite3",
        "subprocess",
        "urllib",
    }
    for path in paths:
        roots = {item.split(".", 1)[0] for item in _imports(path)}
        assert roots.isdisjoint({item.split(".", 1)[0] for item in forbidden})


@pytest.mark.architecture
def test_external_io_is_confined_to_explicit_local_adapter() -> None:
    capable = {
        path.relative_to(SOURCE).as_posix()
        for path in SOURCE.rglob("*.py")
        if _imports(path) & {"http.server", "urllib.request"}
    }
    assert "adapters/release/local.py" in capable
    assert not any(
        path.startswith("domain/") or path.startswith("application/release/") for path in capable
    )


@pytest.mark.architecture
def test_release_has_no_arbitrary_shell_git_or_runtime_private_access() -> None:
    release_paths = [
        SOURCE / "domain" / "release.py",
        *list((SOURCE / "application" / "release").rglob("*.py")),
        SOURCE / "runtime_bridge" / "release.py",
        *list((SOURCE / "adapters" / "release").rglob("*.py")),
    ]
    text = "\n".join(path.read_text(encoding="utf-8") for path in release_paths)
    assert "shell=True" not in text
    assert 'Path(".git")' not in text
    assert ".git/" not in text
    assert "arch_runtime." not in text
    assert "sqlite3" not in text
    assert "Runtime.open" not in text


@pytest.mark.architecture
def test_runtime_bridge_contains_zero_provider_filesystem_network_or_migration_execution() -> None:
    path = SOURCE / "runtime_bridge" / "release.py"
    roots = {name.split(".", 1)[0] for name in _imports(path)}
    assert roots.isdisjoint({"http", "os", "pathlib", "shutil", "socket", "sqlite3", "urllib"})
    text = path.read_text(encoding="utf-8")
    assert ".deploy(" not in text
    assert ".verify(" not in text
    assert ".rollback(" not in text


@pytest.mark.architecture
def test_no_production_credentials_or_raw_secrets_are_committed() -> None:
    forbidden = ("AKIA", "github_pat_", "ghp_", "BEGIN PRIVATE KEY", "password=production")
    for root in (SOURCE, Path("tests/w09")):
        for path in root.rglob("*.py"):
            if path.name in {"workflow.py", "test_architecture.py"}:
                continue
            text = path.read_text(encoding="utf-8")
            assert not any(marker in text for marker in forbidden)


@pytest.mark.architecture
def test_provider_selection_and_strategy_are_explicit_contract_inputs() -> None:
    text = (SOURCE / "application" / "release" / "models.py").read_text(encoding="utf-8")
    assert "provider: DeploymentProviderProfile" in text
    assert "strategy: DeploymentStrategy" in text
    assert "provider: DeploymentProviderProfile | None" not in text
    assert "strategy: DeploymentStrategy | None" not in text
