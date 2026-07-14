# Capability: Generate Part

## What It Does
Turns a plain-English description of a mechanical part into real parametric 3D geometry: an LLM writes CadQuery code, the backend safely executes it (self-repairing up to 3 times on failure), exports STL + STEP + the code, and returns everything needed to render the part in an interactive 3D viewer with the code, repair log and token/cost shown.

## Inputs
| Input | Type | Source | Required |
|-------|------|--------|----------|
| prompt | string (natural-language part description) | user (prompt box) | yes |
| model_id | enum `gemini-2.5-flash` \| `gemini-2.5-pro` | user (model selector) | yes |
| previous_code | string \| null | always null for this capability (set by `modify_part` / `edit_and_rerun`) | no |
| mode | enum `generate` \| `modify` \| `edit` | fixed `generate` for this capability | no |

## Outputs
| Output | Type | Destination |
|--------|------|-------------|
| generated_code | string (final executable CadQuery, fences stripped) | response body + `generated_code/part_<id>/v<n>.py` |
| stl_url / step_url / code_url | string (served under `/artifacts/...`) | response body → 3D viewer + download buttons |
| repair_attempts | list of `{attempt, error, fixed_code_diff_summary}` | response body → repair-attempt panel |
| token_usage | `{prompt_tokens, completion_tokens, total_tokens}` | response body → token/cost panel |
| cost_usd | float (from token usage × per-model rate) | response body → token/cost panel |
| part_id / version_number | string / int | response body; persisted to `parts` + `versions` (see [data.md](../data.md)) |
| status | enum `completed` \| `failed` | response body |

## External Calls
| System | Operation | On Failure |
|--------|-----------|------------|
| Gemini API (`google-genai`) | generate CadQuery code; generate a repair given a traceback | surface error to user; set run status `failed` (no offline fallback) |
| CadQuery / OpenCascade (in-process, sandboxed subprocess) | execute code → export STL + STEP | capture traceback → feed to repair loop (≤3 tries); after 3 → status `failed` |
| Local filesystem | write versioned code + STL + STEP | fatal → status `failed` |

## Business Rules
- The system instruction forces the model to output **only** executable CadQuery Python — no markdown, no prose — assign the final solid to a variable named `result`, and declare parametric named constants at the top for all dimensions. Markdown fences are stripped before execution regardless.
- A **static safety check** runs before every execution and rejects code containing `open(`, `os.`, `sys.`, `subprocess`, `requests`, `socket`, `shutil`, `__import__`, `eval(`, `exec(`, `Path(`, or file/network access. A violation aborts the run (no execution, status `failed`, reason shown).
- Execution runs in a **restricted namespace** with a wall-clock **timeout** (the mechanism is Windows-safe — see [architecture.md](../architecture.md) §Sandbox Design). A timeout is treated as an execution error and feeds the repair loop.
- The generate → safety-check → execute → repair loop retries at most **3** times; the repaired code is re-safety-checked before re-execution.
- Every run is persisted as a new `part` with `version 1` (this capability always starts a fresh chain).

## Success Criteria
- [ ] A real prompt (e.g. "a 60x40x10mm rectangular bracket with two 5mm mounting holes") returns `status=completed` with a non-empty STL and STEP file on disk against the real Gemini key.
- [ ] The exported STL parses as a valid mesh (loadable by three.js `STLLoader`; file size > 0 and mesh has > 0 triangles).
- [ ] When Gemini's first code raises, the repair log shows ≥1 attempt and the final code executes (verified with a prompt crafted to trip a common error, or asserted structurally on the repair-loop bound).
- [ ] Code containing `import os` / `open(` is rejected by the safety check and never executed (status `failed`, reason surfaced).
- [ ] `token_usage.total_tokens > 0` and `cost_usd >= 0` are returned and displayed.
- [ ] The response includes `stl_url`, `step_url`, `code_url` that resolve to downloadable files.
