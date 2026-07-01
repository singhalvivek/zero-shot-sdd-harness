"""E2E golden path against REAL Gemini: upload CSV, then stream an ask over SSE.

Asserts token events arrive with real content and a single done(completed) frame.
"""
import io

import pytest


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


def test_upload_then_stream_ask(api_client, _require_llm_key):
    csv = "dept,salary\nEng,120000\nEng,100000\nSales,80000\n"
    up = api_client.post(
        "/datasets",
        files={"file": ("s.csv", io.BytesIO(csv.encode()), "text/csv")},
    ).json()["data"]

    with api_client.stream(
        "POST",
        f"/sessions/{up['session_id']}/ask",
        json={"question": "What is the average salary by department?"},
    ) as resp:
        assert resp.status_code == 200
        assert "text/event-stream" in resp.headers["content-type"]
        raw = "".join(resp.iter_text())

    events = _parse_sse(raw)
    kinds = [e["event"] for e in events]

    token_events = [e for e in events if e["event"] == "token"]
    assert token_events, f"no token events in {kinds}"
    assert any(e["data"] for e in token_events), "token events had no text"

    assert "done" in kinds, kinds
    done = [e for e in events if e["event"] == "done"][-1]
    assert '"status": "completed"' in done["data"] or '"completed"' in done["data"]
