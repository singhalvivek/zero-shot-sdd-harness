"""Dataframe loading and schema profiling.

Used at upload time. `profile_dataframe` returns ONLY column names + dtypes +
row count — never any cell values — to uphold the rows-never-leave guarantee.
"""
from __future__ import annotations

import pandas as pd


def load_csv(file_path: str) -> pd.DataFrame:
    """Load a CSV file into a pandas DataFrame."""
    return pd.read_csv(file_path)


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
