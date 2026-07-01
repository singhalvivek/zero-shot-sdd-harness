"""Phase-3 persist-timing regression tests.

Reproduces the "resume loses the conversation" race: previously the user +
assistant Message rows were written only AFTER the ~9s stream completed, so a
session resumed mid-stream returned 0 messages. The fix persists the USER turn
EARLY (in _prepare) and the ASSISTANT turn at completion, with exactly one user
row per ask.

Also guards GET /audit against NULL-token AuditLog rows (a run that created its
AuditLog row with status="running" / "failed" but never reached the completing
persist), which used to crash the frontend Audit tab.

The early-persist + audit-null tests are deterministic (no LLM). The full-ask
round-trip test hits REAL Gemini and is gated on _require_llm_key.
"""
import io

import pytest


@pytest.fixture
def seeded_session(api_client):
    csv = "dept,salary\nEngineering,120000\nSales,80000\n"
    r = api_client.post(
        "/datasets",
        files={"file": ("salaries.csv", io.BytesIO(csv.encode()), "text/csv")},
    )
    assert r.status_code == 200, r.text
    return r.json()["data"]["session_id"]


def test_user_turn_persisted_early_before_stream_completes(api_client, seeded_session):
    """_prepare (called before any streaming) must write the user Message row so a
    resumed session immediately shows the question turn — no LLM needed."""
    from graph.runner import _prepare

    sid = seeded_session
    # GET /sessions/{id} shows no messages before the ask.
    before = api_client.get(f"/sessions/{sid}").json()["data"]
    assert before["messages"] == []

    # _prepare runs the early user-turn persist (same code path stream_ask uses
    # before it begins streaming tokens).
    state, run_id = _prepare(sid, "What is the total salary?")
    assert run_id

    # BEFORE the stream (or any assistant answer) the user turn is already
    # queryable via the public resume endpoint.
    detail = api_client.get(f"/sessions/{sid}").json()["data"]
    roles = [m["role"] for m in detail["messages"]]
    assert roles == ["user"], detail["messages"]
    assert detail["messages"][0]["content"] == "What is the total salary?"

    # AuditLog row exists with status=running and NULL tokens at this point.
    audit_rows = api_client.get("/audit", params={"session_id": sid}).json()["data"]
    assert len(audit_rows) == 1
    assert audit_rows[0]["status"] == "running"
    assert audit_rows[0]["prompt_tokens"] is None
    assert audit_rows[0]["completion_tokens"] is None
    assert audit_rows[0]["answer"] is None


def test_audit_endpoint_handles_null_token_running_row(api_client, seeded_session):
    """GET /audit must return a running/failed AuditLog row (NULL tokens) without
    error — the row that used to white-screen the frontend Audit tab."""
    from graph.runner import _prepare

    sid = seeded_session
    _prepare(sid, "anything")  # leaves a status=running, NULL-token audit row

    r = api_client.get("/audit")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ok"] is True
    row = body["data"][0]
    assert row["status"] == "running"
    assert row["prompt_tokens"] is None
    assert row["completion_tokens"] is None


def test_no_duplicate_user_row_after_full_run_ask(
    api_client, seeded_session, _require_llm_key
):
    """After a full ask, exactly ONE user row + ONE assistant row exist — the
    early user persist must not double-write when _persist runs at completion."""
    from graph.runner import run_ask
    from db.session import create_db_session
    from db.models import Message

    sid = seeded_session
    result = run_ask(sid, "What is the total salary?")
    assert result["status"] == "completed", result

    with create_db_session() as s:
        roles = [
            m.role
            for m in s.query(Message)
            .filter(Message.session_id == sid)
            .order_by(Message.created_at.asc())
            .all()
        ]
    assert roles.count("user") == 1, roles
    assert roles.count("assistant") == 1, roles
    assert roles == ["user", "assistant"], roles

    # Both turns resumable via the public endpoint.
    detail = api_client.get(f"/sessions/{sid}").json()["data"]
    assert [m["role"] for m in detail["messages"]] == ["user", "assistant"]


async def test_streaming_user_turn_visible_before_done(
    api_client, seeded_session, _require_llm_key
):
    """Consume stream_ask up to the first token, then assert the user turn is
    already resumable (before `done`) with no assistant row yet — and after the
    stream completes both turns exist with no duplicate user row."""
    from graph.runner import stream_ask

    sid = seeded_session
    agen = stream_ask(sid, "What is the total salary?")

    saw_first_token = False
    async for ev in agen:
        if ev["event"] == "token":
            saw_first_token = True
            # Mid-stream: the user turn is already persisted and resumable.
            detail = api_client.get(f"/sessions/{sid}").json()["data"]
            roles = [m["role"] for m in detail["messages"]]
            assert "user" in roles, roles
            assert roles.count("user") == 1, roles
            # Assistant not yet written (persist happens at completion).
            assert "assistant" not in roles, roles
            break

    assert saw_first_token, "stream produced no token"

    # Drain the rest so the completing persist runs.
    async for _ in agen:
        pass

    detail = api_client.get(f"/sessions/{sid}").json()["data"]
    roles = [m["role"] for m in detail["messages"]]
    assert roles.count("user") == 1, roles
    assert roles.count("assistant") == 1, roles
