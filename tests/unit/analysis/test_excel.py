"""Excel loader + mixed-frame sandbox tests — no LLM key required.

Verifies .xlsx loads schema-only, runs real pandas in the sandbox, and that a
CSV+Excel mixed run executes a cross-frame merge correctly.
"""
import pandas as pd

from analysis.loader import file_type_for, load_excel, load_file, profile_dataframe
from analysis.sandbox import run_pandas


def _write_xlsx(tmp_path, name="sales.xlsx"):
    p = tmp_path / name
    df = pd.DataFrame(
        {
            "dept": ["eng", "eng", "sales", "sales"],
            "salary": [100, 200, 50, 70],
        }
    )
    df.to_excel(p, index=False)
    return str(p)


def test_load_excel_and_profile_schema_only(tmp_path):
    xlsx = _write_xlsx(tmp_path)
    df = load_excel(xlsx)
    prof = profile_dataframe(df)

    assert prof["row_count"] == 4
    names = [c["name"] for c in prof["columns"]]
    assert names == ["dept", "salary"]
    # No cell values anywhere in the schema profile.
    blob = repr(prof)
    for cell in ("eng", "100", "200", "50", "70"):
        assert cell not in blob


def test_file_type_dispatch():
    assert file_type_for("a.csv") == "csv"
    assert file_type_for("a.XLSX") == "xlsx"
    assert file_type_for("a.xls") == "xlsx"


def test_load_file_dispatches_by_extension(tmp_path):
    xlsx = _write_xlsx(tmp_path)
    df = load_file(xlsx)
    assert list(df.columns) == ["dept", "salary"]
    assert len(df) == 4


def test_run_pandas_groupby_on_xlsx(tmp_path):
    xlsx = _write_xlsx(tmp_path)
    code = "result = sales.groupby('dept')['salary'].mean().to_dict()"
    out = run_pandas(code, {"sales": xlsx})

    assert out["ok"] is True, out["error"]
    assert "150.0" in out["result_repr"]  # eng
    assert "60.0" in out["result_repr"]  # sales


def test_mixed_csv_and_xlsx_cross_frame_merge(tmp_path):
    # employees.csv: emp_id -> dept ; salaries.xlsx: emp_id -> salary
    emp = tmp_path / "employees.csv"
    pd.DataFrame(
        {"emp_id": [1, 2, 3, 4], "dept": ["eng", "eng", "sales", "sales"]}
    ).to_csv(emp, index=False)

    sal = tmp_path / "salaries.xlsx"
    pd.DataFrame(
        {"emp_id": [1, 2, 3, 4], "salary": [100, 200, 50, 70]}
    ).to_excel(sal, index=False)

    code = (
        "merged = employees.merge(salaries, on='emp_id')\n"
        "result = merged.groupby('dept')['salary'].sum().to_dict()"
    )
    out = run_pandas(code, {"employees": str(emp), "salaries": str(sal)})

    assert out["ok"] is True, out["error"]
    # eng total = 300, sales total = 120
    assert "300" in out["result_repr"]
    assert "120" in out["result_repr"]
