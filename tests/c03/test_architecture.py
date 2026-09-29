"""C03 dependency and ownership regression tests."""

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
BRIDGES = ROOT / "src" / "arch_web" / "runtime_bridge"


@pytest.mark.architecture
def test_web_bridges_do_not_use_phase_lifecycle_or_private_runtime_storage() -> None:
    sources = "\n".join(path.read_text(encoding="utf-8") for path in BRIDGES.glob("*.py"))
    assert "TransitionDomain.PROJECT_LIFECYCLE" not in sources
    assert "arch_runtime.persistence" not in sources
    assert "sqlite3" not in sources
    assert "repr(" not in sources
    assert "default=str" not in sources


@pytest.mark.architecture
def test_w07_does_not_introduce_a_lifecycle_transition() -> None:
    backend_sources = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (ROOT / "src" / "arch_web").rglob("*backend*.py")
    )
    assert "ApplyTransitionCommand" not in backend_sources
    assert "build_web_transition_command" not in backend_sources
