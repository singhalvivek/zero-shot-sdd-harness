"""Faithful repro of the 2nd-ask native crash over a REAL uvicorn server.

The bug: the streaming path (POST /sessions/{id}/ask -> graph.runner.stream_ask)
hard-crashed the process on the SECOND ask in a session — a native abort with no
Python traceback — because subprocess-spawning + gRPC/absl (google-genai) work
ran on the asyncio event-loop thread. The in-process TestClient streams
synchronously and does NOT reproduce the loop-thread fault, so this test launches
`uv run python -m src` as a tracked subprocess and drives real HTTP/SSE against it.

The server hits REAL Gemini. It is ALWAYS terminated in the fixture teardown; no
listener is left on :8001.
"""
from __future__ import annotations

import io
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import httpx
import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_PORT = 8001
_BASE = f"http://127.0.0.1:{_PORT}"


def _server_python() -> str:
    """Path to the interpreter that runs the server.

    We launch the venv interpreter DIRECTLY (`python -m src`) rather than via
    `uv run`, so the tracked Popen IS the actual server process — terminating it
    cleanly frees :8001 (an intervening `uv run` wrapper would leave the real
    uvicorn python as a surviving grandchild, leaking the listener).
    """
    if os.name == "nt":
        cand = _REPO_ROOT / ".venv" / "Scripts" / "python.exe"
    else:
        cand = _REPO_ROOT / ".venv" / "bin" / "python"
    return str(cand) if cand.exists() else sys.executable


def _kill_tree(proc: subprocess.Popen) -> None:
    """Terminate the server and any children, freeing the port on all platforms."""
    if proc.poll() is None:
        if os.name == "nt":
            subprocess.run(
                ["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                capture_output=True,
            )
        else:
            proc.terminate()
    try:
        proc.wait(timeout=15)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=10)


def _has_llm_key() -> bool:
    from config.settings import get_settings

    s = get_settings()
    return bool(s.anthropic_api_key or s.gemini_api_key)


def _port_is_free(port: int = _PORT) -> bool:
    import socket

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(1.0)
        # If a connect SUCCEEDS, something is already listening -> not free.
        return sock.connect_ex(("127.0.0.1", port)) != 0


def _wait_healthy(proc: subprocess.Popen, log_path: Path, timeout: float = 90.0) -> None:
    deadline = time.monotonic() + timeout
    last_err: Exception | None = None
    while time.monotonic() < deadline:
        if proc.poll() is not None:
            log = log_path.read_text(errors="replace") if log_path.exists() else ""
            raise RuntimeError(
                f"server exited early with code {proc.returncode} before becoming "
                f"healthy. Output:\n{log}"
            )
        try:
            r = httpx.get(f"{_BASE}/health", timeout=2.0)
            if r.status_code == 200:
                return
        except Exception as exc:  # noqa: BLE001
            last_err = exc
        time.sleep(0.5)
    raise RuntimeError(f"server never became healthy within {timeout}s: {last_err}")


@pytest.fixture(scope="module")
def live_server():
    if not _has_llm_key():
        pytest.skip("No LLM key set in .env (AGENT_GEMINI_API_KEY / AGENT_ANTHROPIC_API_KEY)")

    if not _port_is_free():
        raise RuntimeError(
            f"port {_PORT} is already in use before the test starts — a stale "
            "server is listening; kill it before running this test."
        )

    env = dict(os.environ)
    log_fd, log_name = tempfile.mkstemp(prefix="stream_srv_", suffix=".log")
    log_path = Path(log_name)
    log_file = os.fdopen(log_fd, "w")

    # Launch the real uvicorn server (same entrypoint as `uv run python -m src`),
    # binding the venv interpreter directly so teardown reliably frees the port.
    proc = subprocess.Popen(
        [_server_python(), "-m", "src"],
        cwd=str(_REPO_ROOT),
        env=env,
        stdout=log_file,
        stderr=subprocess.STDOUT,
        text=True,
    )
    try:
        _wait_healthy(proc, log_path)
        yield proc
    finally:
        # _kill_tree already terminates the process and waits for it to exit,
        # but call wait() again defensively so no server process leaks and the
        # OS has released the child's inherited handle on the temp log file.
        _kill_tree(proc)
        try:
            proc.wait(timeout=5)
        except Exception:  # noqa: BLE001  (already-reaped or timeout; best-effort)
            pass
        try:
            log_file.close()
        except Exception:  # noqa: BLE001
            pass
        # On Windows the child's inherited handle on the log file may not be
        # released the instant taskkill returns, so unlink() can raise
        # PermissionError [WinError 32]. Retry briefly; if it STILL can't be
        # removed, leaking one temp log must never turn a passing test into an
        # ERROR — swallow ONLY this cleanup failure (not the test body).
        for _attempt in range(10):
            try:
                log_path.unlink(missing_ok=True)
                break
            except PermissionError:
                time.sleep(0.2)


def _parse_sse(raw: str) -> list[dict]:
    events = []
    for block in raw.strip().split("\n\n"):
        ev = {"event": None, "data": ""}
        for line in block.splitlines():
            if line.startswith("event:"):
                ev["event"] = line[len("event:"):].strip()
            elif line.startswith("data:"):
                ev["data"] += line[len("data:"):].strip()
        if ev["event"]:
            events.append(ev)
    return events


def _stream_ask(session_id: str, question: str) -> tuple[list[dict], str]:
    """POST an ask and read the full SSE stream to completion. Returns (events, raw)."""
    with httpx.Client(timeout=180.0) as client:
        with client.stream(
            "POST",
            f"{_BASE}/sessions/{session_id}/ask",
            json={"question": question},
        ) as resp:
            assert resp.status_code == 200, resp.read()
            assert "text/event-stream" in resp.headers["content-type"]
            raw = "".join(resp.iter_text())
    return _parse_sse(raw), raw


def _assert_completed(events: list[dict], label: str) -> str:
    kinds = [e["event"] for e in events]
    tokens = [e for e in events if e["event"] == "token"]
    assert tokens, f"{label}: no token events in {kinds}"
    answer = "".join(e["data"] for e in tokens if e["data"])
    assert answer.strip(), f"{label}: token events had no text ({kinds})"
    assert "done" in kinds, f"{label}: no done frame ({kinds})"
    done = [e for e in events if e["event"] == "done"][-1]
    assert '"completed"' in done["data"], f"{label}: not completed -> {done['data']}"
    return answer


def test_multiple_streaming_asks_do_not_crash_server(live_server):
    """Second (and third) streaming ask in a session must NOT crash the server."""
    proc: subprocess.Popen = live_server

    csv = "dept,salary\nEngineering,120000\nEngineering,100000\nSales,80000\nSales,60000\n"
    with httpx.Client(timeout=60.0) as client:
        up = client.post(
            f"{_BASE}/datasets",
            files={"file": ("s.csv", io.BytesIO(csv.encode()), "text/csv")},
        )
    assert up.status_code == 200, up.text
    session_id = up.json()["data"]["session_id"]

    # First ask — establishes the gRPC background threads in the server process.
    ev1, _ = _stream_ask(session_id, "What is the average salary by department?")
    ans1 = _assert_completed(ev1, "ask#1")
    assert proc.poll() is None, "server died after ask #1"

    # SECOND ask in the SAME session — this is the exact path that crashed before.
    ev2, _ = _stream_ask(session_id, "Now just for the engineering department.")
    ans2 = _assert_completed(ev2, "ask#2")
    assert proc.poll() is None, "server CRASHED after the 2nd ask (the original bug)"

    # THIRD ask — prove stability beyond the 2nd.
    ev3, _ = _stream_ask(session_id, "And what about sales?")
    ans3 = _assert_completed(ev3, "ask#3")
    assert proc.poll() is None, "server died after ask #3"

    # Sanity: real, distinct-ish answers came back from real Gemini.
    assert len(ans1) > 5 and len(ans2) > 5 and len(ans3) > 5

    print(f"\nask#1 answer: {ans1[:200]}")
    print(f"ask#2 answer: {ans2[:200]}")
    print(f"ask#3 answer: {ans3[:200]}")
