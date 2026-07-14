"""Sandbox tests — safety check (unit) + real CadQuery child-process exec.

No LLM/API calls: the CadQuery code is hard-coded. Exercises the Windows-safe
spawn-multiprocessing timeout path deterministically.
"""
import uuid

from sandbox import (
    count_stl_triangles,
    run_and_export,
    static_safety_check,
)

VALID_BOX = """
import cadquery as cq

LENGTH = 20.0
WIDTH = 10.0
HEIGHT = 5.0

result = cq.Workplane("XY").box(LENGTH, WIDTH, HEIGHT)
""".strip()


# --- static_safety_check --------------------------------------------------

def test_safety_allows_valid_cadquery():
    assert static_safety_check(VALID_BOX) is None


def test_safety_allows_math_import():
    code = "import cadquery as cq\nimport math\nresult = cq.Workplane('XY').box(math.pi, 2, 3)"
    assert static_safety_check(code) is None


def test_safety_rejects_import_os():
    code = "import os\nimport cadquery as cq\nresult = cq.Workplane('XY').box(1,1,1)"
    reason = static_safety_check(code)
    assert reason is not None
    assert "os" in reason


def test_safety_rejects_open_call():
    code = "import cadquery as cq\nf = open('x.txt')\nresult = cq.Workplane('XY').box(1,1,1)"
    assert static_safety_check(code) is not None


def test_safety_rejects_os_system_and_subprocess():
    assert static_safety_check("import os\nos.system('dir')") is not None
    assert static_safety_check("import subprocess\nsubprocess.run(['dir'])") is not None


def test_safety_rejects_obfuscated_import_via_dunder():
    # __import__('os') is caught by both substring and AST
    code = "cadquery = __import__('os')\nresult = 1"
    assert static_safety_check(code) is not None


def test_safety_does_not_falsely_flag_pos_dot():
    # `pos.` must NOT trip the `os.` rule (word-boundary regex)
    code = "import cadquery as cq\npos = cq.Vector(1, 2, 3)\nresult = cq.Workplane('XY').box(pos.x, 2, 3)"
    assert static_safety_check(code) is None


def test_safety_rejects_empty_code():
    assert static_safety_check("") is not None
    assert static_safety_check("   ") is not None


# --- run_and_export (real CadQuery child process) -------------------------

def test_run_and_export_writes_valid_stl_and_step(tmp_path):
    part_id = f"test_{uuid.uuid4().hex[:8]}"
    res = run_and_export(VALID_BOX, part_id, 1, formats=("stl", "step"), timeout=30)
    assert res["ok"], res.get("error")
    assert res["stl_path"] and res["step_path"]

    tris = count_stl_triangles(res["stl_path"])
    assert tris > 0
    import os as _os  # test-side only, not sandboxed
    assert _os.path.getsize(res["step_path"]) > 0


def test_run_and_export_reports_missing_result():
    code = "import cadquery as cq\nx = cq.Workplane('XY').box(1, 1, 1)"  # no `result`
    part_id = f"test_{uuid.uuid4().hex[:8]}"
    res = run_and_export(code, part_id, 1, timeout=30)
    assert res["ok"] is False
    assert "result" in res["error"]


def test_run_and_export_reports_exec_error():
    code = "import cadquery as cq\nresult = cq.Workplane('XY').box(1, 1)"  # too few args
    part_id = f"test_{uuid.uuid4().hex[:8]}"
    res = run_and_export(code, part_id, 1, timeout=30)
    assert res["ok"] is False
    assert res["error"]


def test_run_and_export_times_out():
    """An infinite loop is terminated by the Windows-safe process timeout."""
    code = "import cadquery as cq\nwhile True:\n    pass\nresult = 1"
    part_id = f"test_{uuid.uuid4().hex[:8]}"
    res = run_and_export(code, part_id, 1, timeout=3)
    assert res["ok"] is False
    assert "timed out" in res["error"]
