"""Graph integration tests — exercise the full state machine WITHOUT the LLM.

Uses `edit` mode, which enters at static_safety_check with pre-supplied code,
so these run deterministically (real CadQuery child-process exec + export) and
burn no Gemini quota. Real-Gemini coverage lives in tests/phase1/.
"""
import uuid

from graph.agent import agentic_ai

VALID_BOX = """
import cadquery as cq

LENGTH = 30.0
WIDTH = 20.0
HEIGHT = 8.0

result = cq.Workplane("XY").box(LENGTH, WIDTH, HEIGHT)
""".strip()

UNSAFE_CODE = "import os\nresult = os.getcwd()"


def _base_state(code: str, part_id: str) -> dict:
    return {
        "run_id": "run-" + part_id,
        "part_id": part_id,
        "version_number": 1,
        "prompt": "",
        "previous_code": code,
        "model_id": "gemini-3.1-flash-lite",
        "mode": "edit",
        "generated_code": code,
        "attempt_count": 0,
        "repair_attempts": [],
        "token_usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
        "cost_usd": 0.0,
        "error": None,
        "llm_error": False,
    }


def test_graph_executes_valid_code_end_to_end():
    part_id = f"itest_{uuid.uuid4().hex[:8]}"
    final = agentic_ai.invoke(_base_state(VALID_BOX, part_id))
    assert final["status"] == "completed"
    assert final.get("error") is None
    assert final["stl_path"] and final["step_path"]
    assert final["code_path"].endswith("v1.py")

    from sandbox import count_stl_triangles
    assert count_stl_triangles(final["stl_path"]) > 0


def test_graph_blocks_unsafe_code_without_executing():
    part_id = f"itest_{uuid.uuid4().hex[:8]}"
    final = agentic_ai.invoke(_base_state(UNSAFE_CODE, part_id))
    assert final["status"] == "failed"
    assert final.get("safety_violation") is not None
    # Never executed → no artifact paths set.
    assert final.get("stl_path") is None


def test_edit_mode_exec_error_does_not_repair():
    """Bad code in edit mode fails immediately (no repair loop)."""
    part_id = f"itest_{uuid.uuid4().hex[:8]}"
    bad = "import cadquery as cq\nresult = cq.Workplane('XY').box(1, 1)"  # too few args
    final = agentic_ai.invoke(_base_state(bad, part_id))
    assert final["status"] == "failed"
    assert final.get("exec_error")
    assert final.get("repair_attempts") == []
