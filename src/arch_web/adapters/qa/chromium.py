"""Typed local Chromium DevTools adapter for real W08 browser evidence."""

from __future__ import annotations

import base64
import contextlib
import hashlib
import json
import os
import shutil
import socket
import struct
import subprocess
import tempfile
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

from arch_web.application.architecture.planning import semantic_id
from arch_web.domain.qa import QACandidateBaseline, QAResult, QAScenario, QAStatus, ViewportSpec


def _browser_path() -> Path | None:
    candidates = (
        shutil.which("msedge"),
        shutil.which("chrome"),
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    )
    for value in candidates:
        if value is not None and Path(value).is_file():
            return Path(value)
    return None


class _DevToolsSocket:
    def __init__(self, url: str) -> None:
        parsed = urllib.parse.urlsplit(url)
        if parsed.hostname not in {"127.0.0.1", "localhost"}:
            raise ValueError("DevTools endpoint must be loopback")
        self._socket = socket.create_connection((parsed.hostname, parsed.port or 80), timeout=5)
        key = base64.b64encode(os.urandom(16)).decode()
        request = (
            f"GET {parsed.path}?{parsed.query} HTTP/1.1\r\n"
            f"Host: {parsed.hostname}:{parsed.port}\r\n"
            "Upgrade: websocket\r\nConnection: Upgrade\r\n"
            f"Sec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n"
        )
        self._socket.sendall(request.encode("ascii"))
        response = self._recv_until(b"\r\n\r\n")
        if b" 101 " not in response.split(b"\r\n", 1)[0]:
            raise OSError("DevTools WebSocket upgrade failed")
        self._next_id = 1

    def _recv_until(self, marker: bytes) -> bytes:
        data = b""
        while marker not in data:
            chunk = self._socket.recv(4096)
            if not chunk:
                raise OSError("DevTools connection closed")
            data += chunk
        return data

    def _frame(self, payload: bytes) -> bytes:
        first = bytes((0x81,))
        length = len(payload)
        if length < 126:
            header = bytes((0x80 | length,))
        elif length < 65536:
            header = bytes((0xFE,)) + struct.pack("!H", length)
        else:
            header = bytes((0xFF,)) + struct.pack("!Q", length)
        mask = os.urandom(4)
        encoded = bytes(value ^ mask[index % 4] for index, value in enumerate(payload))
        return first + header + mask + encoded

    def _read_exact(self, size: int) -> bytes:
        data = b""
        while len(data) < size:
            chunk = self._socket.recv(size - len(data))
            if not chunk:
                raise OSError("DevTools connection closed")
            data += chunk
        return data

    def _read_message(self) -> dict[str, Any]:
        first, second = self._read_exact(2)
        opcode, length = first & 0x0F, second & 0x7F
        if length == 126:
            length = struct.unpack("!H", self._read_exact(2))[0]
        elif length == 127:
            length = struct.unpack("!Q", self._read_exact(8))[0]
        masked = bool(second & 0x80)
        mask = self._read_exact(4) if masked else b""
        payload = self._read_exact(length)
        if masked:
            payload = bytes(value ^ mask[index % 4] for index, value in enumerate(payload))
        if opcode == 0x8:
            raise OSError("DevTools WebSocket closed")
        if opcode == 0x9:
            self._socket.sendall(bytes((0x8A, 0)))
            return self._read_message()
        decoded: object = json.loads(payload.decode("utf-8"))
        if not isinstance(decoded, dict):
            raise OSError("DevTools message is not an object")
        return {str(key): value for key, value in decoded.items()}

    def call(
        self,
        method: str,
        params: dict[str, object] | None = None,
        *,
        session_id: str | None = None,
    ) -> dict[str, Any]:
        call_id = self._next_id
        self._next_id += 1
        message: dict[str, object] = {
            "id": call_id,
            "method": method,
            "params": params or {},
        }
        if session_id is not None:
            message["sessionId"] = session_id
        payload = json.dumps(message).encode()
        self._socket.sendall(self._frame(payload))
        while True:
            message = self._read_message()
            if message.get("id") == call_id:
                if "error" in message:
                    raise OSError("DevTools command failed")
                result = message.get("result", {})
                if not isinstance(result, dict):
                    raise OSError("DevTools result is not an object")
                return {str(key): value for key, value in result.items()}

    def close(self) -> None:
        self._socket.close()


class LocalChromiumAdapter:
    """Executes exact typed browser actions against a loopback preview."""

    identity = "arch-web.local-chromium-cdp@0.1.0"

    def __init__(self, executable: Path | None = None) -> None:
        self._executable = executable or _browser_path()

    @property
    def available(self) -> bool:
        return self._executable is not None

    def execute(
        self,
        scenario: QAScenario,
        candidate: QACandidateBaseline,
        endpoint: str,
        viewport: ViewportSpec,
    ) -> QAResult:
        if self._executable is None:
            return self._result(
                scenario,
                candidate,
                viewport,
                QAStatus.INCONCLUSIVE,
                0,
                (),
                ("browser_tool_unavailable",),
                "unavailable",
            )
        parsed = urllib.parse.urlsplit(endpoint)
        if parsed.hostname not in {"127.0.0.1", "localhost"}:
            raise ValueError("Browser QA endpoint must be loopback")
        with socket.socket() as reservation:
            reservation.bind(("127.0.0.1", 0))
            devtools_port = int(reservation.getsockname()[1])
        with tempfile.TemporaryDirectory(
            prefix="arch-web-qa-", ignore_cleanup_errors=True
        ) as profile:
            command = [
                str(self._executable),
                "--headless=new",
                "--disable-gpu",
                "--disable-breakpad",
                "--disable-crash-reporter",
                "--no-first-run",
                "--no-default-browser-check",
                "--noerrdialogs",
                f"--remote-debugging-port={devtools_port}",
                f"--user-data-dir={profile}",
                "about:blank",
            ]
            process = subprocess.Popen(
                command,
                cwd=profile,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                text=True,
                shell=False,
            )
            socket_client: _DevToolsSocket | None = None
            stage = "devtools_endpoint"
            try:
                websocket = self._read_endpoint(process, devtools_port)
                stage = "websocket_handshake"
                socket_client = _DevToolsSocket(websocket)
                stage = "browser_version"
                version = socket_client.call("Browser.getVersion")
                browser_identity = str(version.get("product", "chromium-unknown"))
                targets = socket_client.call("Target.getTargets")
                page_target = next(
                    item
                    for item in targets.get("targetInfos", ())
                    if isinstance(item, dict) and item.get("type") == "page"
                )
                attached = socket_client.call(
                    "Target.attachToTarget",
                    {"targetId": str(page_target["targetId"]), "flatten": True},
                )
                session_id = str(attached["sessionId"])
                stage = "page_setup"
                socket_client.call("Page.enable", session_id=session_id)
                socket_client.call("Runtime.enable", session_id=session_id)
                socket_client.call(
                    "Page.addScriptToEvaluateOnNewDocument",
                    {
                        "source": """
window.__archErrors = [];
window.addEventListener('error', e => window.__archErrors.push(String(e.message)));
window.addEventListener('unhandledrejection', e => window.__archErrors.push('unhandled'));
const originalError = console.error;
console.error = (...args) => { window.__archErrors.push('console'); originalError(...args); };
"""
                    },
                    session_id=session_id,
                )
                socket_client.call(
                    "Emulation.setDeviceMetricsOverride",
                    {
                        "width": viewport.width,
                        "height": viewport.height,
                        "deviceScaleFactor": 1,
                        "mobile": viewport.touch,
                    },
                    session_id=session_id,
                )
                route = next(step.target for step in scenario.steps if step.action == "navigate")
                url = urllib.parse.urljoin(endpoint, route.lstrip("/"))
                stage = "navigation"
                socket_client.call("Page.navigate", {"url": url}, session_id=session_id)
                time.sleep(0.5)
                expression = """
(() => {
  const button = document.querySelector('#state-toggle');
  button?.focus();
  const focused = document.activeElement === button;
  button?.click();
  const resources = performance.getEntriesByType('resource').map(x => x.name);
  const external = resources.filter(x => !x.startsWith(location.origin));
  return {
    main: Boolean(document.querySelector('main')),
    feedback: document.querySelector('#feedback')?.textContent || '',
    focused,
    overflow: document.documentElement.scrollWidth <= window.innerWidth,
    errors: window.__archErrors || [],
    external
  };
})()
"""
                stage = "interaction"
                evaluated = socket_client.call(
                    "Runtime.evaluate",
                    {"expression": expression, "returnByValue": True},
                    session_id=session_id,
                )
                value = dict(evaluated["result"].get("value", {}))
                stage = "screenshot"
                screenshot = socket_client.call(
                    "Page.captureScreenshot",
                    {"format": "png"},
                    session_id=session_id,
                )
                screenshot_bytes = base64.b64decode(str(screenshot.get("data", "")))
                checks = {
                    "landmark": bool(value.get("main")),
                    "interaction": value.get("feedback") == "Selected",
                    "focus": bool(value.get("focused")),
                    "overflow": bool(value.get("overflow")),
                    "runtime_errors": not value.get("errors"),
                    "external_requests": not value.get("external"),
                    "screenshot": bool(screenshot_bytes),
                }
                diagnostics = tuple(
                    f"{name}:{'pass' if passed else 'fail'}"
                    for name, passed in sorted(checks.items())
                )
                status = QAStatus.PASS if all(checks.values()) else QAStatus.FAIL
                digest = "sha256:" + hashlib.sha256(screenshot_bytes).hexdigest()
                return self._result(
                    scenario,
                    candidate,
                    viewport,
                    status,
                    len(checks),
                    (digest,),
                    diagnostics,
                    browser_identity,
                )
            except (OSError, KeyError, ValueError) as error:
                return self._result(
                    scenario,
                    candidate,
                    viewport,
                    QAStatus.INCONCLUSIVE,
                    0,
                    (),
                    (f"browser_execution_inconclusive:{stage}:{type(error).__name__}",),
                    self._executable.name,
                )
            finally:
                if socket_client is not None:
                    with contextlib.suppress(OSError):
                        socket_client.call("Browser.close")
                    socket_client.close()
                if process.poll() is None:
                    process.terminate()
                    try:
                        process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait(timeout=5)

    @staticmethod
    def _read_endpoint(process: subprocess.Popen[str], port: int) -> str:
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            try:
                with urllib.request.urlopen(
                    f"http://127.0.0.1:{port}/json/version", timeout=0.25
                ) as response:
                    payload: object = json.loads(response.read().decode("utf-8"))
                if isinstance(payload, dict):
                    endpoint = payload.get("webSocketDebuggerUrl")
                    if isinstance(endpoint, str):
                        return endpoint
            except (OSError, json.JSONDecodeError):
                time.sleep(0.05)
        raise OSError("Browser DevTools endpoint unavailable")

    def _result(
        self,
        scenario: QAScenario,
        candidate: QACandidateBaseline,
        viewport: ViewportSpec,
        status: QAStatus,
        assertions: int,
        digests: tuple[str, ...],
        diagnostics: tuple[str, ...],
        browser_identity: str,
    ) -> QAResult:
        return QAResult(
            semantic_id(
                "QRS",
                {
                    "scenario": scenario.scenario_id,
                    "candidate": candidate.canonical_fingerprint(),
                    "viewport": viewport.viewport_id,
                    "status": status,
                    "evidence": digests,
                },
            ),
            scenario.scenario_id,
            candidate.canonical_fingerprint(),
            candidate.source_tree_fingerprint,
            candidate.git_head,
            browser_identity,
            viewport.viewport_id,
            status,
            (status,),
            assertions,
            digests,
            diagnostics,
        )


__all__ = ("LocalChromiumAdapter",)
