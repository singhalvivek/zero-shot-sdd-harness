# Capability: Ask a Question About the CSV

## What It Does
Answers one plain-language question about the session's uploaded CSV by having the LLM write real pandas code, executing it in a sandbox, critiquing/retrying on failure or low confidence (bounded), and composing a plain-language answer with the actual computed numbers embedded — or plainly stating it can't answer, never fabricating a number.

## Inputs
| Input | Type | Source | Required |
|-------|------|--------|----------|
| session_id | string | URL path (`/sessions/{session_id}/messages`) | yes |
| question | string | Request body | yes |
| session DataFrame + prior messages | in-memory | Session store, looked up by `session_id` | yes (session must exist) |

## Outputs
| Output | Type | Destination |
|--------|------|-------------|
| answer | string (plain language) | Returned to the browser; rendered as an assistant chat bubble |
| status | enum("completed", "failed") | Returned alongside `answer`; drives whether the UI shows a normal bubble or an error banner |

## External Calls
| System | Operation | On Failure |
|--------|-----------|------------|
| Anthropic API (`write_code`, `critique`, `compose_answer` nodes) | generate code / judge outcome / compose prose | fatal — graph routes to `handle_error`, API returns `status: "failed"` with a plain error, never a raw stack trace |
| In-process pandas sandbox | execute the generated code against the session's DataFrame copy | non-fatal for user-code errors (feeds the retry loop); fatal only if the sandbox harness itself cannot run |
| SQLite (`analysis_runs`) | log the question/answer/status for observability | non-fatal — logged, answer still returned |

## Business Rules
- The agent must execute real pandas code against the actual uploaded data before answering — a number in the answer must trace back to a `result` value produced by `execute_code`, never a value the LLM invented directly in `compose_answer`.
- If the first generated code attempt errors or the critique step judges it insufficient, the agent retries with corrected code, up to `max_iterations` (default 3) attempts total, before giving up.
- If a question references a column that does not exist in the session's schema, or is otherwise unanswerable from the available data, the final answer must plainly say the agent doesn't have enough information/context to answer — it must never guess or fabricate a number.
- No intermediate code, stdout, or critique reasoning is ever included in the API response or shown in the UI — only the final `answer` text.
- Each question is answered with awareness of the session's prior chat turns (see `conversation-memory`), so follow-up questions can omit context already established.
- The agent is purely reactive: it answers only the question asked and never appends unsolicited follow-up suggestions or additional analysis to the answer.

## Success Criteria
- [ ] Asking a concrete, answerable question (e.g. "what is the total of column X?") returns `status: "completed"` with an answer whose embedded number matches an independent `df["X"].sum()` computation on the same file.
- [ ] A gate test forces at least one real retry: a question phrased so the first LLM attempt is plausibly wrong/errors (e.g. ambiguous column reference) still ends in a correct answer, and structured logs show `iterations > 1` for that request.
- [ ] Asking about a nonexistent column returns `status: "completed"` with an answer stating the agent lacks the information/column — never a fabricated number, and never a raw exception message.
- [ ] The API response body never contains a `code` field, sandbox stdout, or critique text.
- [ ] A fatal failure (simulated LLM outage) returns `status: "failed"` with a plain-language error, not a raw 500 stack trace.
