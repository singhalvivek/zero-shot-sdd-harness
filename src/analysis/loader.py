"""Dataframe loading and schema profiling.

Used at upload time. `profile_dataframe` returns ONLY column names + dtypes +
row count — never any cell values — to uphold the rows-never-leave guarantee.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

_EXCEL_SUFFIXES = (".xlsx", ".xls")


def load_csv(file_path: str) -> pd.DataFrame:
    """Load a CSV file into a pandas DataFrame."""
    return pd.read_csv(file_path)


def load_excel(file_path: str) -> pd.DataFrame:
    """Load an Excel workbook (first sheet) into a pandas DataFrame.

    Uses openpyxl (a project dependency) for .xlsx; pandas selects the engine.
    """
    return pd.read_excel(file_path, sheet_name=0)


def file_type_for(file_path: str) -> str:
    """Return the canonical file_type ('csv' or 'xlsx') for a path by extension."""
    suffix = Path(file_path).suffix.lower()
    if suffix in _EXCEL_SUFFIXES:
        return "xlsx"
    return "csv"


def load_file(file_path: str, file_type: str | None = None) -> pd.DataFrame:
    """Dispatch to the right reader for .csv or .xlsx/.xls.

    If file_type is omitted it is inferred from the path extension.
    """
    ft = (file_type or file_type_for(file_path)).lower()
    if ft in ("xlsx", "xls", "excel"):
        return load_excel(file_path)
    return load_csv(file_path)


def profile_dataframe(df: pd.DataFrame) -> dict:
    """Return schema-only metadata: {row_count, columns: [{name, dtype}]}.

    Deliberately contains NO cell values — only structural schema that is safe
    to send to the LLM.
    """
    return {
        "row_count": int(len(df)),
        "columns": [
            {"name": str(name), "dtype": str(dtype)}
            for name, dtype in df.dtypes.items()
        ],
    }
