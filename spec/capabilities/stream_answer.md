# Capability: Stream Answer

## What It Does
Turns the agent's aggregate result into a plain-language answer with the key number(s) called out, and streams it token-by-token to the browser over SSE, capturing token usage.

## Inputs
| Input | Type | Source | Required |
|-------|------|--------|----------|
| exec_result | dict | `execute` node output | yes |
| question | str | agent state | yes |
| schemas + messages | dict / list | agent state | yes |

## Outputs
| Output | Type | Destination |
|--------|------|-------------|
| `token` events | SSE `{text}` | browser, repeatedly during the answer node |
| `usage` event | SSE `{prompt_tokens, completion_tokens}` | browser |
| `done` event | SSE `{run_id, status}` | browser, once at end |
| `error` event | SSE `{message}` | browser, on terminal failure |

## External Calls
| System | Operation | On Failure |
|--------|-----------|------------|
| Gemini | streamed answer generation | retry → `error` event via `handle_error` |

## Business Rules
- The answer phrases the aggregate result in plain language and explicitly calls out the key number(s).
- Token usage is captured from Gemini metadata and accumulated into the AuditLog row; the UI display may be a labelled stub in Phase 1.
- A mid-stream failure surfaces as an SSE `error` event (the HTTP stream has already started), never a silent stop.

## Success Criteria
- [ ] Asking a question yields a sequence of `token` SSE events that concatenate to the full answer, followed by exactly one `done` event.
- [ ] The streamed answer text contains the key number(s) from the aggregate result.
- [ ] Token usage is recorded on the `AuditLog` row for the run.
- [ ] A forced failure produces an SSE `error` event and a graceful UI message, not a hung stream.
