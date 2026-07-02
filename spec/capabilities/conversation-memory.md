# Capability: Conversation Memory Within a Session

## What It Does
Keeps the full chat history (all prior questions and answers) for the active session available to every subsequent question, so follow-up questions that omit explicit context (e.g. "and the average?" after "what's the total revenue?") are answered correctly.

## Inputs
| Input | Type | Source | Required |
|-------|------|--------|----------|
| session_id | string | URL path | yes |
| prior messages | list of `{role, content}` | Session store's `Session.messages` | yes (may be empty for the first question) |

## Outputs
| Output | Type | Destination |
|--------|------|-------------|
| history | list of `{role, content}` | Passed into the `write_code` and `compose_answer` LLM prompts for the current question |
| updated messages list | list | The session store, appended with the new user question and assistant answer once the turn completes |

## External Calls
| System | Operation | On Failure |
|--------|-----------|------------|
| In-memory session store | read `messages` (via `load_context`) and append the new turn (via `finalize`) | non-fatal — a failed append is logged; the current answer is still returned to the user, though it may be missing from history for the *next* question |

## Business Rules
- History is scoped strictly to one session (one `session_id`); there is no cross-session memory.
- History does not persist across a server restart or a new browser tab — a fresh session starts with empty history, per the product brief.
- History is passed to the LLM in full (uncompressed) in Phase 1 — no summarization or windowing.
- Only the user's question text and the assistant's final plain-language answer are stored in history — never the intermediate code, sandbox output, or critique text.

## Success Criteria
- [ ] After asking "what is the total revenue?" and receiving an answer, asking "and what's the average?" in the same session returns a correct average for the same column without the user re-specifying the column name.
- [ ] A brand-new session (new upload, new `session_id`) started in the same server process has empty history and does not "remember" a previous session's questions.
- [ ] The `messages` list returned by `GET /sessions/{session_id}` after two questions contains exactly 4 entries (2 user, 2 assistant) in chronological order, with only question/answer text — no code or intermediate content.
