"""Managed path security and tree determinism."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest
from hypothesis import given
from hypothesis import strategies as st

from arch_web import (
    FileEvidence,
    RepositoryBaseline,
    WebContractValidationError,
    WorkspaceBaseline,
)
from arch_web.workspace_paths import confined_path, normalize_managed_path
from w05.factories import workspace_command


@pytest.mark.parametrize(
    "value",
    [
        "/etc/passwd",
        "../escape",
        "a/../b",
        "C:\\temp\\x",
        "D:/x",
        "\\\\server\\share",
        ".git/config",
        ".arch-web/state",
        "a//b",
        " a",
    ],
)
def test_unsafe_managed_paths_are_rejected(value: str) -> None:
    with pytest.raises(WebContractValidationError):
        normalize_managed_path(value)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("src/app/main.py", "src/app/main.py"),
        ("src\\app\\main.py", "src/app/main.py"),
        (".env.example", ".env.example"),
    ],
)
def test_safe_paths_are_canonical(value: str, expected: str) -> None:
    assert normalize_managed_path(value) == expected


@given(st.lists(st.from_regex(r"[a-z][a-z0-9_-]{0,8}", fullmatch=True), min_size=1, max_size=5))
def test_safe_path_segments_remain_confined(parts: list[str]) -> None:
    value = "/".join(parts)
    assert normalize_managed_path(value) == value


def test_link_escape_is_rejected(tmp_path: Path) -> None:
    root = tmp_path / "root"
    outside = tmp_path / "outside"
    root.mkdir()
    outside.mkdir()
    try:
        (root / "link").symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip("Symlink creation is unavailable")
    with pytest.raises(WebContractValidationError, match="link"):
        confined_path(root, "link/file.txt")


def test_link_escape_logic_is_platform_independent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "root"
    outside = tmp_path / "outside"
    root.mkdir()
    outside.mkdir()
    original_exists = Path.exists
    original_resolve = Path.resolve

    def exists(path: Path) -> bool:
        return path.name == "link" or original_exists(path)

    def resolve(path: Path, strict: bool = False) -> Path:
        if path.name == "link":
            return outside
        return original_resolve(path, strict=strict)

    monkeypatch.setattr(Path, "exists", exists)
    monkeypatch.setattr(Path, "is_symlink", lambda path: path.name == "link")
    monkeypatch.setattr(Path, "resolve", resolve)
    with pytest.raises(WebContractValidationError, match="link"):
        confined_path(root, "link/file.txt")


def test_tree_manifest_is_ordered_and_excludes_tooling(tmp_path: Path) -> None:
    (tmp_path / "z.txt").write_text("z", encoding="utf-8")
    (tmp_path / "a.txt").write_text("a", encoding="utf-8")
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "node_modules" / "ignored.js").write_text("x", encoding="utf-8")
    command = workspace_command(tmp_path)
    assert [item.path for item in command.baseline.files] == ["a.txt", "z.txt"]
    assert all("node_modules" not in item.path for item in command.baseline.files)


def test_case_collision_fails_closed() -> None:
    evidence = workspace_command(Path("unused")).baseline.files
    with pytest.raises(ValueError, match="case-colliding"):
        WorkspaceBaseline(
            "w",
            "p",
            True,
            (replace(evidence[0], path="A") if evidence else _file("A"), _file("a")),
            "tree",
            RepositoryBaseline(False, None, None, False),
        )


def _file(path: str) -> FileEvidence:
    return FileEvidence(path, "sha256:" + "a" * 64, 1)
