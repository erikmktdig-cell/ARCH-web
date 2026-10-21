"""Bounded endpoint discovery belongs to the launched browser's private profile."""

from pathlib import Path
from unittest.mock import Mock

import pytest

from arch_web import LocalChromiumAdapter, QAStatus
from arch_web.adapters.qa import chromium
from w08.factories import qa_bundle


def clock(monkeypatch: pytest.MonkeyPatch) -> list[float]:
    now = [0.0]
    monkeypatch.setattr("arch_web.adapters.qa.chromium.time.monotonic", lambda: now[0])
    monkeypatch.setattr(
        "arch_web.adapters.qa.chromium.time.sleep",
        lambda seconds: now.__setitem__(0, now[0] + seconds),
    )
    return now


def test_endpoint_is_read_from_private_profile(tmp_path: Path) -> None:
    (tmp_path / "DevToolsActivePort").write_text(
        "45678\n/devtools/browser/abc-123\n", encoding="ascii"
    )
    process = Mock()
    process.poll.return_value = None
    assert (
        LocalChromiumAdapter._read_endpoint(process, tmp_path)
        == "ws://127.0.0.1:45678/devtools/browser/abc-123"
    )


def test_partial_publication_is_polled_within_same_deadline(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    now = clock(monkeypatch)
    path = tmp_path / "DevToolsActivePort"
    process = Mock()
    process.poll.return_value = None

    def publish(seconds: float) -> None:
        now[0] += seconds
        path.write_text(
            "45678\n" if now[0] < 0.1 else "45678\n/devtools/browser/abc-123\n", encoding="ascii"
        )

    monkeypatch.setattr("arch_web.adapters.qa.chromium.time.sleep", publish)
    assert LocalChromiumAdapter._read_endpoint(process, tmp_path).startswith(
        "ws://127.0.0.1:45678/"
    )
    assert now[0] == 0.1


def test_live_cold_start_can_publish_after_old_ten_second_limit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    now = clock(monkeypatch)
    process = Mock()
    process.poll.return_value = None

    def publish(seconds: float) -> None:
        now[0] += seconds
        if now[0] >= 12:
            (tmp_path / "DevToolsActivePort").write_text(
                "45678\n/devtools/browser/abc-123\n", encoding="ascii"
            )

    monkeypatch.setattr("arch_web.adapters.qa.chromium.time.sleep", publish)
    assert LocalChromiumAdapter._read_endpoint(process, tmp_path).startswith(
        "ws://127.0.0.1:45678/"
    )
    assert 12 <= now[0] < 12.1


@pytest.mark.parametrize(
    "content",
    [
        b"",
        b"0\n/devtools/browser/abc",
        b"65536\n/devtools/browser/abc",
        b"-1\n/devtools/browser/abc",
        b"123\nws://example.invalid/abc",
        b"123\n/devtools/browser/abc?secret=token",
        b"123\n/devtools/browser/abc\nextra",
        b"\xff",
        b"123\n/devtools/browser/" + b"a" * 2000,
    ],
)
def test_invalid_endpoint_never_connects_and_times_out(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, content: bytes
) -> None:
    now = clock(monkeypatch)
    (tmp_path / "DevToolsActivePort").write_bytes(content)
    process = Mock()
    process.poll.return_value = None
    with pytest.raises(chromium._EndpointTimeoutError):
        LocalChromiumAdapter._read_endpoint(process, tmp_path)
    assert 30 <= now[0] < 30.1


def test_exited_browser_cannot_use_stale_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    now = clock(monkeypatch)
    (tmp_path / "DevToolsActivePort").write_text("123\n/devtools/browser/abc", encoding="ascii")
    process = Mock()
    process.poll.return_value = 1
    with pytest.raises(chromium._BrowserExitedError):
        LocalChromiumAdapter._read_endpoint(process, tmp_path)
    assert now[0] == 0


def test_missing_endpoint_times_out(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    now = clock(monkeypatch)
    process = Mock()
    process.poll.return_value = None
    with pytest.raises(chromium._EndpointTimeoutError):
        LocalChromiumAdapter._read_endpoint(process, tmp_path)
    assert 30 <= now[0] < 30.1


def test_browser_owns_port_and_startup_failure_remains_inconclusive(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, prepared, profile = qa_bundle(tmp_path)
    process = Mock()
    process.poll.return_value = 1
    launch = Mock(return_value=process)
    monkeypatch.setattr("arch_web.adapters.qa.chromium.subprocess.Popen", launch)
    reservation = Mock(side_effect=AssertionError("adapter must not reserve then release a port"))
    monkeypatch.setattr("arch_web.adapters.qa.chromium.socket.socket", reservation)
    result = LocalChromiumAdapter(Path("chrome")).execute(
        prepared.scope.scenarios[0],
        prepared.candidate,
        "http://127.0.0.1:9000/",
        profile.viewport_policy.viewports[0],
    )
    assert result.status is QAStatus.INCONCLUSIVE
    assert result.sanitized_diagnostics == (
        "browser_execution_inconclusive:devtools_endpoint:_BrowserExitedError",
    )
    launch.assert_called_once()
    reservation.assert_not_called()
    command = launch.call_args.args[0]
    assert "--remote-debugging-port=0" in command
    assert not Path(launch.call_args.kwargs["cwd"]).exists()
