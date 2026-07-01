# UI

---

## UI Type

Single-page web chat-style analysis console. Next.js 15 + React 19 + Tailwind, static export served at `:8001/app/`.

## Views / Screens

### Screen: Analysis Console (single page)

**Purpose:** Upload data and have a conversation about it.

**Key elements:**
- **Upload panel (REAL, P1):** drop/select a CSV; shows filename, row count, column list once profiled.
- **Question box (REAL, P1):** text input + Ask button.
- **Answer stream (REAL, P1):** streamed plain-language answer with key numbers; analysis code is NOT shown.
- **Conversation thread (REAL, P1):** prior question/answer turns in the session (conversation memory).
- **Second-file upload (STUB, P1 → real P3):** labelled "Multi-file — coming soon".
- **Excel toggle (STUB, P1 → real P3):** labelled "Excel — coming soon".
- **Clarifying-question prompt (STUB, P1 → real P2):** inline area where the agent's clarifying question will appear.
- **Follow-up chips (STUB, P1 → real P2):** 2–3 suggested follow-up buttons.
- **Token-usage badge (STUB, P1 → real P2):** per-query prompt/completion token count.
- **Audit-log tab (STUB, P1 → real P2):** past queries with timestamps.
- **Session switcher (STUB, P1 → real P3):** resume a prior session.

> Every stub carries a visible "Coming soon" badge / disabled styling so it is never mistaken for a bug.

**Actions available:**
- Upload a CSV (P1), ask a question (P1), click a follow-up chip (P2), open the audit tab (P2), switch sessions (P3).

## Error States
- Upload error: inline red banner ("Could not read this file — is it a valid CSV?").
- Ask error: the answer panel shows the SSE `error` message; the question stays editable to retry.
- Loading: streamed tokens appear progressively; a spinner shows while the agent plans/executes before the first token.

## Tech Stack

Next.js 15 + React 19 + Tailwind CSS. SSE consumed via `EventSource`/fetch streaming. E2E tests in `frontend/tests/e2e/` with Playwright; the Phase 1 smoke test covers upload → ask → streamed answer.
