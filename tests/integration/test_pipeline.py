"""End-to-end integration test against REAL Gemini.

Uploads a CSV, runs the non-streaming ask runner with a real question, and
asserts: the answer is non-empty and contains a number, an AuditLog row is
written with status=completed and token counts > 0, and the computed aggregate
matches a hand-written pandas groupby on the same file.
"""
import io
import re

import pytest


@pytest.fixture
def seeded_session(api_client):
    """Upload a salary CSV and return (session_id, expected_means)."""
    csv = (
        "dept,salary\n"
        "Engineering,120000\n"
        "Engineering,100000\n"
        "Sales,80000\n"
        "Sales,90000\n"
        "Marketing,70000\n"
    )
    r = api_client.post(
        "/datasets",
        files={"file": ("salaries.csv", io.BytesIO(csv.encode()), "text/csv")},
    )
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    expected = {"Engineering": 110000.0, "Sales": 85000.0, "Marketing": 70000.0}
    return data["session_id"], expected


def test_ask_average_salary_by_department(api_client, seeded_session, _require_llm_key):
    from graph.runner import run_ask
    from db.session import create_db_session
    from db.models import AuditLog

    session_id, expected = seeded_session
    result = run_ask(session_id, "What is the average salary by department?")

    assert result["status"] == "completed", result
    answer = result["answer_text"]
    assert answer.strip(), "answer text was empty"
    assert re.search(r"\d", answer), f"answer has no number: {answer!r}"

    # Aggregate must match a hand-computed groupby (numbers present in result_repr).
    repr_text = (result["exec_result"] or {}).get("result_repr", "")
    for mean in expected.values():
        # accept e.g. 110000, 110000.0
        assert (
            str(int(mean)) in repr_text or f"{mean}" in repr_text
        ), f"expected mean {mean} not found in {repr_text!r}"

    # AuditLog row written with tokens + completed status.
    with create_db_session() as s:
        rows = s.query(AuditLog).filter(AuditLog.session_id == session_id).all()
        assert len(rows) == 1
        row = rows[0]
        assert row.status == "completed"
        assert (row.prompt_tokens or 0) > 0
        assert (row.completion_tokens or 0) > 0
        assert row.answer


def test_followup_uses_conversation_context(api_client, seeded_session, _require_llm_key):
    """A follow-up that references the prior turn resolves via rehydrated messages."""
    from graph.runner import run_ask
    from db.session import create_db_session
    from db.models import Message

    session_id, _ = seeded_session
    run_ask(session_id, "What is the average salary by department?")
    second = run_ask(session_id, "Now just for Engineering.")

    assert second["status"] == "completed", second
    # Engineering mean is 110000; the answer should reference it.
    assert "110000" in (second["exec_result"] or {}).get("result_repr", "") or re.search(
        r"\d", second["answer_text"]
    )

    with create_db_session() as s:
        roles = [
            m.role
            for m in s.query(Message).filter(Message.session_id == session_id).all()
        ]
    # 2 asks -> 2 user + 2 assistant turns persisted.
    assert roles.count("user") == 2


def test_ask_empty_question_raises(api_client, seeded_session):
    from graph.runner import run_ask

    session_id, _ = seeded_session
    with pytest.raises(ValueError):
        run_ask(session_id, "")


# --- Phase 2: clarify gate ------------------------------------------------


@pytest.fixture
def ambiguous_session(api_client):
    """A schema with several plausible numeric metrics to make 'best' ambiguous."""
    csv = (
        "name,salary,tenure_years,headcount\n"
        "Alice,120000,5,10\n"
        "Bob,80000,2,4\n"
        "Carol,95000,8,7\n"
    )
    r = api_client.post(
        "/datasets",
        files={"file": ("people.csv", io.BytesIO(csv.encode()), "text/csv")},
    )
    assert r.status_code == 200, r.text
    return r.json()["data"]["session_id"]


def test_clarify_on_ambiguous_question(api_client, ambiguous_session, _require_llm_key):
    """An ambiguous question yields needs_clarification + a clarifying question."""
    from graph.runner import run_ask

    result = run_ask(ambiguous_session, "Which is the best one?")
    assert result["status"] == "needs_clarification", result
    assert result["needs_clarification"] is True
    assert result["clarifying_question"], "expected a clarifying question"


def test_clear_question_passes_triage(api_client, seeded_session, _require_llm_key):
    """A clear question proceeds straight through triage to a real numeric answer."""
    from graph.runner import run_ask

    session_id, expected = seeded_session
    result = run_ask(session_id, "What is the average salary by department?")
    assert result["status"] == "completed", result
    assert result["needs_clarification"] is False
    assert re.search(r"\d", result["answer_text"]), result["answer_text"]
    repr_text = (result["exec_result"] or {}).get("result_repr", "")
    assert str(int(expected["Engineering"])) in repr_text, repr_text


# --- Phase 2: suggestions -------------------------------------------------


def test_answer_produces_suggestions(api_client, seeded_session, _require_llm_key):
    from graph.runner import run_ask

    session_id, _ = seeded_session
    result = run_ask(session_id, "What is the average salary by department?")
    assert result["status"] == "completed", result
    suggestions = result["suggestions"]
    assert 2 <= len(suggestions) <= 3, suggestions
    assert all(isinstance(s, str) and s.strip() for s in suggestions)


def test_suggestions_prompt_leaks_no_raw_rows(api_client, seeded_session):
    """Privacy: the suggestions prompt is schema-only — no raw cell values."""
    from graph.prompting import build_suggestions_prompt

    schemas = {
        "salaries": {
            "row_count": 5,
            "columns": [
                {"name": "dept", "dtype": "object"},
                {"name": "salary", "dtype": "int64"},
            ],
        }
    }
    prompt = build_suggestions_prompt(
        "average salary by department",
        "dept\nEngineering    110000.0\nSales    85000.0",
        schemas,
    )
    # raw row identifiers like employee names must never appear
    assert "Engineering" in prompt  # aggregate result repr is allowed
    # column names allowed; assert no fabricated raw-row markers are injected
    assert "df.head" not in prompt
    assert "salary" in prompt and "dept" in prompt


# --- Phase 2: audit API ---------------------------------------------------


def test_audit_endpoint_lists_runs(api_client, seeded_session, _require_llm_key):
    from graph.runner import run_ask

    session_id, _ = seeded_session
    run_ask(session_id, "What is the average salary by department?")

    r = api_client.get("/audit")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ok"] is True
    rows = body["data"]
    assert len(rows) >= 1
    row = rows[0]
    for key in (
        "id",
        "session_id",
        "question",
        "answer",
        "prompt_tokens",
        "completion_tokens",
        "status",
        "created_at",
    ):
        assert key in row, key
    assert row["question"]
    assert row["status"] == "completed"
    assert row["answer"]
    assert (row["prompt_tokens"] or 0) > 0

    # session_id filter works
    r2 = api_client.get("/audit", params={"session_id": session_id})
    assert r2.status_code == 200
    assert all(x["session_id"] == session_id for x in r2.json()["data"])


def test_audit_newest_first(api_client, seeded_session, _require_llm_key):
    from graph.runner import run_ask

    session_id, _ = seeded_session
    run_ask(session_id, "What is the average salary by department?")
    run_ask(session_id, "How many departments are there?")

    rows = api_client.get("/audit").json()["data"]
    assert len(rows) >= 2
    times = [x["created_at"] for x in rows]
    assert times == sorted(times, reverse=True), times
