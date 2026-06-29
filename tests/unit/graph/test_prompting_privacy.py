"""Privacy guard: prompt builders must NEVER include raw cell values.

The builders only accept schema metadata (column names, dtypes, row_count) and
aggregate result reprs — never a DataFrame or raw rows. These tests assert that
even when sensitive-looking cell values exist, they cannot reach a prompt because
the builders are not given any rows.
"""
from graph.prompting import (
    build_answer_prompt,
    build_plan_prompt,
    build_refine_prompt,
    build_write_code_prompt,
    extract_python,
    format_schemas,
)

SCHEMA = {
    "employees": {
        "row_count": 3,
        "columns": [
            {"name": "name", "dtype": "object"},
            {"name": "salary", "dtype": "int64"},
            {"name": "dept", "dtype": "object"},
        ],
    }
}

# Sensitive cell values that must NEVER appear in any prompt.
SECRETS = ["Alice", "Bob", "Carol", "99999", "secret@email.com"]


def _assert_no_secrets(text: str) -> None:
    for secret in SECRETS:
        assert secret not in text, f"leaked cell value {secret!r} into prompt"


def test_format_schemas_only_has_structure():
    rendered = format_schemas(SCHEMA)
    assert "salary" in rendered and "int64" in rendered and "3 rows" in rendered
    _assert_no_secrets(rendered)


def test_plan_prompt_no_cell_values():
    p = build_plan_prompt("average salary by dept", SCHEMA, messages=[])
    _assert_no_secrets(p)
    assert "salary" in p


def test_write_code_prompt_no_cell_values():
    p = build_write_code_prompt("avg salary", "step 1", SCHEMA)
    _assert_no_secrets(p)


def test_refine_prompt_no_cell_values():
    p = build_refine_prompt("avg salary", "plan", "code", "KeyError", SCHEMA)
    _assert_no_secrets(p)


def test_answer_prompt_only_uses_aggregate():
    # The answer prompt only ever receives an aggregate repr, not raw rows.
    p = build_answer_prompt("avg salary", "dept\nEng    85000\nName: salary", messages=[])
    assert "85000" in p  # aggregate is allowed
    _assert_no_secrets(p)


def test_extract_python_pulls_fenced_block():
    text = "Here you go:\n```python\nresult = df.mean()\n```\nDone"
    assert extract_python(text) == "result = df.mean()"
