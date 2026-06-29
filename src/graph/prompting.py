"""Prompt builders for the analysis graph.

PRIVACY GUARD: every builder here takes ONLY schema metadata (column names,
dtypes, row counts) and aggregate result reprs. None of these functions accept a
raw DataFrame or cell values, so by construction no raw row can enter a prompt.
The execute node is the only place data is touched, and it runs locally in the
sandbox — its output is an aggregate `result_repr`, not raw rows.
"""
from __future__ import annotations

from pathlib import Path

_PROMPTS = Path(__file__).parent.parent / "prompts"


def load_prompt(name: str) -> str:
    return (_PROMPTS / f"{name}.md").read_text(encoding="utf-8").strip()


def format_schemas(schemas: dict[str, dict]) -> str:
    """Render schema-only context: df name, row count, columns + dtypes."""
    lines: list[str] = []
    for df_name, schema in schemas.items():
        row_count = schema.get("row_count", "unknown")
        lines.append(f"Dataframe `{df_name}` ({row_count} rows):")
        for col in schema.get("columns", []):
            lines.append(f"  - {col['name']}: {col['dtype']}")
    return "\n".join(lines)


def format_messages(messages: list | None, limit: int = 6) -> str:
    """Render recent prior turns (sliding window) — these are user/assistant text,
    never raw data rows."""
    if not messages:
        return ""
    recent = messages[-limit:]
    rendered = "\n".join(f"{m['role']}: {m['content']}" for m in recent)
    return f"\nPrior conversation:\n{rendered}\n"


def build_plan_prompt(question: str, schemas: dict, messages: list | None = None) -> str:
    return (
        f"{format_messages(messages)}"
        f"Schema:\n{format_schemas(schemas)}\n\n"
        f"Question: {question}"
    )


def build_write_code_prompt(question: str, plan: str, schemas: dict) -> str:
    return (
        f"Schema:\n{format_schemas(schemas)}\n\n"
        f"Plan:\n{plan}\n\n"
        f"Question: {question}"
    )


def build_refine_prompt(question: str, plan: str, code: str, error: str, schemas: dict) -> str:
    return (
        f"Schema:\n{format_schemas(schemas)}\n\n"
        f"Plan:\n{plan}\n\n"
        f"Previous code:\n{code}\n\n"
        f"Error:\n{error}\n\n"
        f"Question: {question}"
    )


def build_answer_prompt(question: str, result_repr: str, messages: list | None = None) -> str:
    return (
        f"{format_messages(messages)}"
        f"Question: {question}\n\n"
        f"Computed result:\n{result_repr}"
    )


def extract_python(text: str) -> str:
    """Pull the pandas code out of a fenced ```python block; fall back to raw text."""
    if "```" not in text:
        return text.strip()
    body = text.split("```", 2)
    inner = body[1] if len(body) >= 2 else text
    if inner.startswith("python"):
        inner = inner[len("python"):]
    return inner.strip()
