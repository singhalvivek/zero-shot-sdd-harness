"""Sandbox + loader unit tests — no LLM key required.

Verifies the isolated subprocess sandbox runs real pandas, captures errors, and
that neither the sandbox surface nor the profiler leaks raw cell values.
"""
import pandas as pd

from analysis.loader import load_csv, profile_dataframe
from analysis.sandbox import run_pandas


def _write_csv(tmp_path):
    p = tmp_path / "sales.csv"
    df = pd.DataFrame(
        {
            "dept": ["eng", "eng", "sales", "sales"],
            "salary": [100, 200, 50, 70],
        }
    )
    df.to_csv(p, index=False)
    return str(p)


def test_run_pandas_groupby_real(tmp_path):
    csv = _write_csv(tmp_path)
    code = "result = sales.groupby('dept')['salary'].mean().to_dict()"
    out = run_pandas(code, {"sales": csv})

    assert out["ok"] is True
    assert out["error"] is None
    # eng mean = 150.0, sales mean = 60.0
    assert "150.0" in out["result_repr"]
    assert "60.0" in out["result_repr"]
    assert "eng" in out["result_repr"]


def test_run_pandas_broken_code_returns_error(tmp_path):
    csv = _write_csv(tmp_path)
    code = "result = sales['does_not_exist'].sum()"
    out = run_pandas(code, {"sales": csv})

    assert out["ok"] is False
    assert out["error"]
    assert "KeyError" in out["error"] or "does_not_exist" in out["error"]
    assert out["result_repr"] == ""


def test_run_pandas_timeout(tmp_path):
    csv = _write_csv(tmp_path)
    code = "import time; time.sleep(5); result = 1"
    out = run_pandas(code, {"sales": csv}, timeout=1)

    assert out["ok"] is False
    assert "timed out" in out["error"].lower()


def test_run_pandas_only_surfaces_result_not_raw_rows(tmp_path):
    """Aggregate-only: the function must surface ONLY the computed aggregate,
    never the individual raw row values (200, 70) that were not aggregated."""
    csv = _write_csv(tmp_path)
    code = "result = int(sales['salary'].sum())"
    out = run_pandas(code, {"sales": csv})

    assert out["ok"] is True
    assert out["result_repr"] == "420"
    # The raw per-row values must not appear anywhere the LLM would see.
    surfaced = out["result_repr"] + out["stdout"]
    for raw in ("200", "70"):
        assert raw not in surfaced


def test_code_is_not_shell_interpolated(tmp_path):
    """A code body containing shell metacharacters must run as Python, safely."""
    csv = _write_csv(tmp_path)
    code = "result = 'a; rm -rf /; $(whoami)'"
    out = run_pandas(code, {"sales": csv})
    assert out["ok"] is True
    assert "rm -rf" in out["result_repr"]


def test_profile_dataframe_schema_only_no_values(tmp_path):
    csv = _write_csv(tmp_path)
    df = load_csv(csv)
    prof = profile_dataframe(df)

    assert prof["row_count"] == 4
    names = [c["name"] for c in prof["columns"]]
    assert names == ["dept", "salary"]
    dtypes = {c["name"]: c["dtype"] for c in prof["columns"]}
    assert "int" in dtypes["salary"]
    assert dtypes["dept"] in ("object", "str")

    # No cell values anywhere in the profile.
    blob = repr(prof)
    for cell in ("eng", "sales", "100", "200", "50", "70"):
        # column name "sales" is the df_name, not in profile; cell tokens absent
        assert cell not in blob
