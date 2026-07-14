"""Phase 1 acceptance — real Gemini + real CadQuery, end to end.

Keeps real-API volume LOW: ONE generation total (gemini-3.1-flash-lite). The
safety-check (e) and repair-bound (f) assertions are unit-level (no API call).
"""
import os

import pytest

BRACKET_PROMPT = "a 60x40x10mm rectangular bracket with two 5mm mounting holes"


@pytest.mark.usefixtures("_require_gemini_key")
def test_generate_part_end_to_end(api_client):
    """(a) POST /runs → completed; (b) STL has >0 triangles; (c) STEP non-empty;
    (d) token_usage.total_tokens > 0 and cost_usd >= 0."""
    r = api_client.post(
        "/runs",
        json={"prompt": BRACKET_PROMPT, "model_id": "gemini-3.1-flash-lite"},
    )
    assert r.status_code == 200, r.text
    data = r.json()["data"]

    # (a) status completed
    assert data["status"] == "completed", data.get("error")
    assert data["part_id"]
    assert data["version_number"] == 1
    assert data["generated_code"] and "result" in data["generated_code"]

    # URLs present
    assert data["stl_url"] and data["stl_url"].endswith("part_v1.stl")
    assert data["step_url"] and data["step_url"].endswith("part_v1.step")
    assert data["code_url"] and data["code_url"].endswith("v1.py")

    # (b) STL exists and parses as a mesh with > 0 triangles
    from sandbox import count_stl_triangles, exports_dir

    part_dir = exports_dir(data["part_id"])
    stl_file = str(part_dir / "part_v1.stl")
    step_file = str(part_dir / "part_v1.step")
    assert os.path.exists(stl_file), stl_file
    assert count_stl_triangles(stl_file) > 0

    # (c) STEP exists and is non-empty
    assert os.path.exists(step_file), step_file
    assert os.path.getsize(step_file) > 0

    # (d) tokens + cost
    assert data["token_usage"]["total_tokens"] > 0
    assert data["cost_usd"] >= 0.0

    # The persisted run is re-fetchable with the same shape.
    got = api_client.get(f"/runs/{data['run_id']}")
    assert got.status_code == 200
    assert got.json()["data"]["stl_url"] == data["stl_url"]


def test_safety_check_rejects_import_os_without_executing():
    """(e) Code containing `import os` is rejected by the safety check, no exec."""
    from sandbox import static_safety_check

    reason = static_safety_check(
        "import os\nimport cadquery as cq\nresult = cq.Workplane('XY').box(1,1,1)"
    )
    assert reason is not None
    assert "os" in reason


def test_repair_loop_is_bounded_at_three():
    """(f) The repair loop bound lives in after_execute and stops at 3."""
    from graph.edges import after_execute

    # Under the bound → keep repairing.
    assert (
        after_execute({"exec_error": "err", "attempt_count": 2, "mode": "generate"})
        == "repair_on_error"
    )
    # At the bound → stop.
    assert (
        after_execute({"exec_error": "err", "attempt_count": 3, "mode": "generate"})
        == "handle_error"
    )
