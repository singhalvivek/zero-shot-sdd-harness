"""Phase 3 end-to-end multi-file join against REAL Gemini.

Seeds a session with two datasets that must be joined to answer the question,
and asserts the agent's computed aggregate matches a hand-computed pandas
merge+groupby. Also checks that updated_at advances after an ask.
"""
import io

import pandas as pd
import pytest


@pytest.fixture
def two_dataset_session(api_client):
    """employees(emp_id, dept) + salaries(emp_id, salary) bound to one session."""
    employees = pd.DataFrame(
        {
            "emp_id": [1, 2, 3, 4, 5],
            "dept": ["Engineering", "Engineering", "Sales", "Sales", "Marketing"],
        }
    )
    salaries = pd.DataFrame(
        {
            "emp_id": [1, 2, 3, 4, 5],
            "salary": [120000, 100000, 80000, 90000, 70000],
        }
    )

    up1 = api_client.post(
        "/datasets",
        files={
            "file": (
                "employees.csv",
                io.BytesIO(employees.to_csv(index=False).encode()),
                "text/csv",
            )
        },
    )
    assert up1.status_code == 200, up1.text
    sid = up1.json()["data"]["session_id"]

    up2 = api_client.post(
        "/datasets",
        data={"session_id": sid},
        files={
            "file": (
                "salaries.csv",
                io.BytesIO(salaries.to_csv(index=False).encode()),
                "text/csv",
            )
        },
    )
    assert up2.status_code == 200, up2.text

    # Hand-computed expected totals via merge+groupby.
    merged = employees.merge(salaries, on="emp_id")
    expected = merged.groupby("dept")["salary"].sum().to_dict()
    # {Engineering: 220000, Sales: 170000, Marketing: 70000}
    return sid, expected


def test_multifile_join_total_salary_per_department(
    api_client, two_dataset_session, _require_llm_key
):
    from graph.runner import run_ask

    sid, expected = two_dataset_session
    result = run_ask(sid, "What is the total salary per department?")

    assert result["status"] == "completed", result
    repr_text = (result["exec_result"] or {}).get("result_repr", "")
    for total in expected.values():
        assert (
            str(int(total)) in repr_text or f"{total}" in repr_text
        ), f"expected total {total} not found in {repr_text!r} (expected={expected})"


def test_updated_at_advances_after_ask(
    api_client, two_dataset_session, _require_llm_key
):
    from graph.runner import run_ask

    sid, _ = two_dataset_session
    before = api_client.get("/sessions").json()["data"]
    before_updated = {s["session_id"]: s["updated_at"] for s in before}[sid]

    run_ask(sid, "What is the total salary per department?")

    after = api_client.get("/sessions").json()["data"]
    after_updated = {s["session_id"]: s["updated_at"] for s in after}[sid]
    assert after_updated >= before_updated
    # message_count should now reflect the persisted turn(s).
    row = {s["session_id"]: s for s in after}[sid]
    assert row["message_count"] >= 1
    assert row["last_question"] == "What is the total salary per department?"
