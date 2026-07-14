# Capability: Edit and Re-run

## What It Does
Lets the user hand-edit the generated CadQuery code in an in-browser code editor and re-run it through the same safety + execution + export pipeline, re-rendering the result — no LLM call involved.

## Inputs
| Input | Type | Source | Required |
|-------|------|--------|----------|
| part_id | string | current part | yes |
| code | string (user-edited CadQuery) | in-browser code editor | yes |
| model_id | enum | carried for cost display; unused for exec | no |

## Outputs
| Output | Type | Destination |
|--------|------|-------------|
| new version_number | int | `versions` row (`source = "edit"`, `parent_version_id` = version edited) |
| stl_url, step_url, code_url, status | same shape as `generate_part` (no `token_usage`/`cost` — no LLM call) | response body → viewer + panels |
| safety_violation / exec_error | string \| null | response body → error panel |

## External Calls
| System | Operation | On Failure |
|--------|-----------|------------|
| CadQuery / OpenCascade (sandboxed subprocess) | execute + export | on exec error, return the traceback to the editor (NO LLM repair — the user is driving) |
| Local filesystem | write versioned code + STL + STEP | fatal → status `failed` |

## Business Rules
- The `edit` mode **skips `generate_code`**: the user's code enters the graph directly at the static safety check.
- The same static safety check and Windows-safe timeout apply — user-edited code is not trusted.
- On execution failure the raw traceback is returned to the editor; the LLM repair loop is **not** invoked (the human is editing, not the model).
- A successful re-run creates a new version linked to the edited version.

## Success Criteria
- [ ] Editing a dimension constant and re-running produces a new version with changed geometry, no LLM call (`token_usage` absent / zero).
- [ ] Edited code containing a forbidden call (`import os`) is rejected by the safety check and not executed.
- [ ] A syntax error in edited code returns the traceback to the editor without a repair attempt and without creating a valid STL.
