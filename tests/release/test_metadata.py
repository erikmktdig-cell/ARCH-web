from __future__ import annotations

import tomllib
from pathlib import Path
from typing import cast

import pytest

pytestmark = pytest.mark.release
ROOT = Path(__file__).parents[2]


def _project() -> dict[str, object]:
    with (ROOT / "pyproject.toml").open("rb") as stream:
        config = tomllib.load(stream)
    return cast(dict[str, object], config["project"])


def test_release_metadata_is_frozen() -> None:
    project = _project()
    assert project["name"] == "arch-web"
    assert project["requires-python"] == ">=3.12,<3.14"
    assert project["dynamic"] == ["version"]
    assert project["dependencies"] == ["arch-runtime>=0.1.0,<0.2.0"]
    assert project["urls"] == {
        "Repository": "https://github.com/erikmktdig-cell/ARCH-web",
        "Issues": "https://github.com/erikmktdig-cell/ARCH-web/issues",
        "Changelog": "https://github.com/erikmktdig-cell/ARCH-web/blob/main/CHANGELOG.md",
    }


def test_python_requirement_and_classifiers_agree() -> None:
    project = _project()
    classifiers = cast(list[str], project["classifiers"])
    assert "Programming Language :: Python :: 3.12" in classifiers
    assert "Programming Language :: Python :: 3.13" in classifiers


def test_security_policy_uses_private_reporting() -> None:
    policy = (ROOT / "SECURITY.md").read_text(encoding="utf-8")
    assert "security/advisories/new" in policy
    assert "public issues" in policy


def test_ci_is_least_privilege_and_covers_supported_platforms() -> None:
    workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    assert "permissions:\n  contents: read" in workflow
    assert "os: [ubuntu-latest, windows-latest]" in workflow
    assert 'python: ["3.12", "3.13"]' in workflow
    assert "persist-credentials: false" in workflow
    assert "pip-audit" in workflow
    assert "continue-on-error" not in workflow
    assert "|| true" not in workflow
    assert "secrets." not in workflow
    assert "uses: actions/checkout@v" not in workflow
    assert "uses: actions/setup-python@v" not in workflow


def test_lock_has_no_editable_or_local_checkout_source() -> None:
    with (ROOT / "uv.lock").open("rb") as stream:
        lock = tomllib.load(stream)
    packages = {item["name"]: item for item in cast(list[dict[str, object]], lock["package"])}
    assert packages["arch-web"]["source"] == {"editable": "."}
    assert packages["arch-runtime"]["source"] == {
        "git": "https://github.com/erikmktdig-cell/ARCH-runtime.git?tag=v0.1.0#16e2426e61a19bf695f36f01b94a93f8b0276e18"
    }
    assert packages["arch-kernel"]["source"] == {
        "git": "https://github.com/erikmktdig-cell/ARCH-kernel.git?tag=v0.1.0#08b9c9bd57d90ee12a6b40e350431ca1c3bb8bc0"
    }
