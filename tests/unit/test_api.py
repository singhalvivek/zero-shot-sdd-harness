"""API contract tests — no LLM key required (run_agent is mocked)."""
import json
from unittest.mock import patch

from sqlalchemy.orm import Session


def _fake_result(run_id: str, part_id: str = "part-1") -> dict:
    return {
        "run_id": run_id,
        "part_id": part_id,
        "version_number": 1,
        "status": "completed",
        "generated_code": "import cadquery as cq\nresult = cq.Workplane('XY').box(1,1,1)",
        "repair_attempts": [],
        "safety_violation": None,
        "token_usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
        "cost_usd": 0.0001,
        "stl_url": f"/artifacts/exports/part_{part_id}/part_v1.stl",
        "step_url": f"/artifacts/exports/part_{part_id}/part_v1.step",
        "code_url": f"/artifacts/code/part_{part_id}/v1.py",
        "error": None,
        "llm_error": False,
    }


def test_health(api_client):
    r = api_client.get("/health")
    assert r.status_code == 200
    assert r.json()["data"]["status"] == "ok"


def test_post_runs_happy_path_shape(api_client):
    with patch("api.runs.run_agent", return_value=_fake_result("run-1")):
        r = api_client.post(
            "/runs", json={"prompt": "a box", "model_id": "gemini-3.5-flash"}
        )
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["status"] == "completed"
    assert data["part_id"] == "part-1"
    assert data["stl_url"].endswith("part_v1.stl")
    assert data["step_url"].endswith("part_v1.step")
    assert data["code_url"].endswith("v1.py")
    assert data["token_usage"]["total_tokens"] == 15


def test_post_runs_empty_prompt_rejected(api_client):
    r = api_client.post("/runs", json={"prompt": "  ", "model_id": "gemini-3.5-flash"})
    assert r.status_code == 400
    assert r.json()["detail"]["code"] == "INVALID_PROMPT"


def test_post_runs_invalid_model_rejected(api_client):
    r = api_client.post("/runs", json={"prompt": "a box", "model_id": "gpt-4"})
    assert r.status_code == 400
    assert r.json()["detail"]["code"] == "INVALID_MODEL"


def test_post_runs_missing_prompt_field(api_client):
    r = api_client.post("/runs", json={"model_id": "gemini-3.5-flash"})
    assert r.status_code == 422  # pydantic validation


def test_post_runs_pipeline_failure_is_200(api_client):
    failed = _fake_result("run-2")
    failed.update(
        {"status": "failed", "safety_violation": "forbidden token: 'os.'", "stl_url": None,
         "error": "safety_violation: forbidden token: 'os.'"}
    )
    with patch("api.runs.run_agent", return_value=failed):
        r = api_client.post(
            "/runs", json={"prompt": "hack the fs", "model_id": "gemini-3.5-flash"}
        )
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["status"] == "failed"
    assert data["safety_violation"] is not None
    assert data["stl_url"] is None


def test_post_runs_llm_unreachable_is_502(api_client):
    failed = _fake_result("run-3")
    failed.update({"status": "failed", "llm_error": True, "error": "gemini_error: auth"})
    with patch("api.runs.run_agent", return_value=failed):
        r = api_client.post(
            "/runs", json={"prompt": "a box", "model_id": "gemini-3.5-flash"}
        )
    assert r.status_code == 502
    assert r.json()["detail"]["code"] == "LLM_UNREACHABLE"


def test_get_run_not_found(api_client):
    r = api_client.get("/runs/nonexistent-id")
    assert r.status_code == 404


def test_get_run_returns_persisted_json(api_client, _isolated_db):
    from db.models import RunRow

    result = _fake_result("stored-run")
    with Session(_isolated_db) as s:
        row = RunRow(id="stored-run", status="completed", output_text=json.dumps(result))
        s.add(row)
        s.commit()

    r = api_client.get("/runs/stored-run")
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["run_id"] == "stored-run"
    assert data["stl_url"].endswith("part_v1.stl")
