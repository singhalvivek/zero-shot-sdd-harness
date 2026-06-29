# Capability: Ask Question

## What It Does
Runs the LangGraph agent on a natural-language question over the session's bound dataset — plan, write pandas, execute it locally in a sandbox, refine on error — producing a correct aggregate result, while keeping raw rows local.

## Inputs
| Input | Type | Source | Required |
|-------|------|--------|----------|
| session_id | str (uuid) | URL path | yes |
| question | str | `POST /sessions/{id}/ask` body | yes |
| dataset schema + path | dict | session's bound Dataset | yes |
| prior messages | list | session `Message` history | no |

## Outputs
| Output | Type | Destination |
|--------|------|-------------|
| aggregate result | dict (`exec_result`) | feeds the answer node (in-graph) |
| Message rows | DB | SQLite `Message` (user + assistant turns) |
| AuditLog row | DB | SQLite `AuditLog` (question, answer, tokens, status) |

## External Calls
| System | Operation | On Failure |
|--------|-----------|------------|
| Gemini | plan / write_code / refine LLM calls | retry x3 → set `error` → `handle_error` |
| Sandbox (`run_pandas`) | execute generated pandas in subprocess | captured error → `refine` (≤ MAX_REFINES) |
| SQLite | append Message + AuditLog | log + fail run |

## Business Rules
- Only column names, dtypes, row count, and aggregate results enter prompts — never raw rows or cell values.
- The execute↔refine loop is bounded by `MAX_REFINES` (default 3); after the cap, route to a best-effort/error answer.
- Prior conversation turns are rehydrated so follow-ups ("break that down by region") resolve without restating the subject.
- The computed number must match a hand-written pandas result on the same file.

## Success Criteria
- [ ] Asking "average salary by department" returns numbers equal to a hand-computed pandas groupby on the same CSV.
- [ ] A follow-up that references the prior turn ("now just for Engineering") answers correctly using conversation context.
- [ ] When the first generated code errors, the run refines and still produces a correct answer within MAX_REFINES.
- [ ] No prompt sent to Gemini contains a raw data row (verifiable in the structured log).
- [ ] One `AuditLog` row with token counts and `status="completed"` is written per successful ask.
