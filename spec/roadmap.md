# Roadmap

## What This Agent Does

A personal CSV data-analysis chat agent. The user uploads a single CSV file, then asks a series of plain-language questions about it in one continuous chat session. Each question is answered by an agent that writes and executes real pandas code against the uploaded file, inspects the result, and retries if the first attempt fails or looks wrong — then replies with a plain-language answer that has the real, code-verified numbers embedded in the prose. It never fabricates a number: if it can't answer confidently (missing column, unanswerable question), it says so plainly.

## Who Uses It

A single person working alone on their own machine/session — no teams, no multi-tenant concerns, no auth. They have one CSV (a spreadsheet export, a report, a dataset) and want quick answers without opening Excel or writing their own pandas code.

## Core Problem Being Solved

Answering ad-hoc questions about a CSV today means opening a spreadsheet tool or writing one-off pandas/SQL, both of which are slower than just asking the question in plain language. Naively asking an LLM "what's the average X" without execution risks a hallucinated number. This agent replaces that manual step with a chat interface backed by real code execution, so answers are both fast and numerically trustworthy.

## Success Criteria

- [ ] A user can upload a CSV (≤10MB) and receive confirmation (filename, row count, column names) within a few seconds.
- [ ] A user can ask a plain-language question about the uploaded CSV and receive a plain-language answer containing a number/fact that is verifiably correct against the file (i.e., independently computable with pandas and matching).
- [ ] When the first generated analysis attempt errors or looks wrong, the agent retries with a corrected approach before answering — this is observable via structured logs/trace showing >1 execution attempt on at least one gate test case.
- [ ] When a question references a nonexistent column or is unanswerable from the data, the agent responds that it doesn't have enough information/context — never a fabricated number.
- [ ] A user can ask a second, related question in the same session and the agent's answer reflects awareness of the earlier turn (e.g., "and what about the top one?" resolves using prior context).
- [ ] No intermediate code or reasoning steps are ever shown to the user — only the final plain-language answer text (plus a spinner while working).

## What This Agent Does NOT Do (Out of Scope)

- Multiple/concurrent CSV files in one session (single file per session only).
- Charts, plots, or any visual output — text answers only.
- Exporting results to a file (CSV, PDF, etc.).
- Proactive profiling or follow-up-question suggestions on upload or after an answer — the agent is purely reactive.
- Persisting sessions, chat history, or uploaded files across a server restart or across browser tabs/devices — no login, no cross-device sync.
- Multi-user access control, sharing, or team workspaces.
- Editing or transforming the source CSV (read-only analysis).
- Surfacing the generated pandas code or intermediate reasoning steps to the user.

## Key Constraints

- Single-user, no authentication, no per-user data isolation beyond the ephemeral session.
- Files are small (a few MB); latency is not a primary concern, but the sandboxed execution loop must still bound retries and wall-clock time per question so a bad LLM-generated code attempt can't hang the request indefinitely.
- Experimental/prototype quality is acceptable — occasional imperfect answers are tolerable, but the "no fabricated numbers" and "say when you don't know" rules are non-negotiable, since they are the whole point of the tool.
- No production database or data-residency requirements; server-side code execution against the uploaded file and outbound LLM API calls are both acceptable.

## Phases of Development

> **Phase 1 is the smallest first-time-right user-testable win.** It must work perfectly the first time the user tests it — zero rough edges on the tested path. Its backend is minimal but REAL on the one core path (no fake data on the tested path). Its frontend is visually complete: real UI for the one working path PLUS clearly-labelled NON-FUNCTIONAL stubs for everything coming later, so the user sees the vision (a stub must never be mistaken for a bug). Each later phase wires those stubs into real functionality, one increment at a time.

### Phase 1 — Upload + Chat Q&A with Verified Analysis

- **Goal:** the user opens the web UI, uploads a small CSV, asks a question in a chat box, and gets back a correct plain-language answer produced by real pandas execution against the actual file (not a guess) — and can keep asking follow-up questions in the same session with conversation memory intact.
- **Capabilities delivered:** `upload-csv`, `ask-question` (code-execution reasoning loop), `conversation-memory`. See [`spec/capabilities/index.md`](capabilities/index.md).
- **Independent slices (parallel build units):**
  - `slice-db-migration` (backend) — Alembic migration adding `session_id`, `question`/`answer` semantics to the `analysis_runs` table (new table; the skeleton's `runs` table is left untouched so existing tests keep passing). Owns `alembic/versions/`, `src/db/models.py` (add `AnalysisRunRow`). Deps: none.
  - `slice-session-sandbox` (backend) — in-memory session store (CSV → DataFrame + chat history, keyed by `session_id`) and the restricted pandas execution sandbox. Owns `src/session/store.py` (new), `src/analysis/sandbox.py` (new). Deps: none.
  - `slice-graph` (backend) — the LangGraph reasoning/refinement graph and its nodes/edges/state, replacing the `transform_text` skeleton capability slot. Owns `src/graph/state.py`, `src/graph/nodes.py`, `src/graph/edges.py`, `src/graph/agent.py`, `src/graph/runner.py`, `src/prompts/*.md` (new prompt files). Deps: reads the interfaces of `slice-session-sandbox` (the sandbox's function signature and session-store accessor) — build against an agreed interface stub so it can start in parallel, wire the real import last.
  - `slice-api` (backend) — FastAPI routes for upload and chat, replacing `/runs`. Owns `src/api/uploads.py` (new), `src/api/chat.py` (new), `src/api/__init__.py` (router registration), `src/domain/analysis.py` (new Pydantic request/response models). Deps: calls into `slice-graph`'s runner and `slice-session-sandbox`'s store — same interface-stub approach, wire real imports last.
  - `slice-frontend` (frontend) — replaces the transform form in `frontend/src/app/page.tsx` with an upload step + chat UI (message list, input box, spinner), plus clearly-labelled stub UI affordances for future features (chart/export buttons, disabled with a "coming soon" tooltip). Owns `frontend/src/app/page.tsx`, new `frontend/src/app/components/` (ChatPanel, UploadPanel), `frontend/tests/e2e/chat-journey.spec.ts` (new). Deps: none (calls the API by contract, not by import).
- **Key surfaces / files:**
  - Backend creates: `src/analysis/sandbox.py`, `src/analysis/__init__.py`, `src/session/store.py`, `src/session/__init__.py`, `src/api/uploads.py`, `src/api/chat.py`, `src/domain/analysis.py`, `src/prompts/write_code.md`, `src/prompts/critique.md`, `src/prompts/compose_answer.md`, `alembic/versions/0002_analysis_runs.py`.
  - Backend modifies: `src/graph/state.py`, `src/graph/nodes.py`, `src/graph/edges.py`, `src/graph/agent.py`, `src/graph/runner.py`, `src/db/models.py`, `src/api/__init__.py`, `src/config/settings.py` (add fast-model + timeout/max-iteration env vars).
  - Backend leaves untouched: `src/api/health.py`, `src/db/session.py`, `src/llm/client.py`, `src/llm/providers/*`, `src/api/_common.py`, `src/api/runs.py`/`RunRow` (kept for the existing skeleton smoke tests; not used by this capability).
  - Frontend modifies: `frontend/src/app/page.tsx`.
  - Frontend creates: `frontend/src/app/components/UploadPanel.tsx`, `frontend/src/app/components/ChatPanel.tsx`, `frontend/tests/e2e/chat-journey.spec.ts`.
- **Gate command:** `uv run alembic upgrade head && uv run pytest tests/unit tests/integration/test_pipeline.py -q` (backend, real Anthropic key from `.env`, SQLite per `AGENT_DATABASE_URL`) **and** `cd frontend && pnpm build && cd .. && uv run python -m src` then `npx playwright test frontend/tests/e2e/ --reporter=line` (frontend, against the live app at `http://localhost:8001/app/`).
- **How the user tests it (handoff seed):**
  1. `cd frontend && pnpm build` then from repo root `uv run python -m src`.
  2. Open `http://localhost:8001/app/`.
  3. Upload the sample CSV (any CSV with a numeric column, e.g. an orders/sales export). Confirm the upload panel shows filename, row count, and column names — this is REAL (parsed by the backend).
  4. In the chat box, ask a concrete question, e.g. "what is the total revenue?" or "which row has the highest value in column X?". Expect a plain-language answer with the actual number embedded, after a brief spinner (no intermediate steps shown).
  5. Ask a follow-up that depends on the first answer's context, e.g. "and what's the average?" — expect it to answer without re-stating the column name, proving conversation memory.
  6. Ask a question referencing a column that doesn't exist, e.g. "what's the total for `nonexistent_column`?" — expect a plain-language "I don't have enough information to answer that" style response, never a fabricated number.
  7. Labelled stubs (visible but non-functional, clearly marked "coming soon"): a disabled "Export answer" button and a disabled "Show chart" toggle next to the chat input — these are NOT wired to anything in Phase 1.

### Phase 2 — Robustness & Answer Quality (sketch)

Not fully sliced yet; detailed at the start of Phase 2 once Phase 1 is human-approved. Expected scope, drawn from remaining/out-of-scope items:

- Surface clearer, more specific error messages for edge cases (malformed CSV, empty file, non-UTF8 encoding) instead of a generic failure.
- Tune the retry/critique loop using real usage feedback (adjust `max_iterations`, prompt wording) based on where Phase 1 answers were wrong or slow.
- Optionally: lightweight text-only "shape of the data" facts (row/column counts, dtypes) available on request, still purely reactive (no proactive profiling).
- Optionally: session inactivity TTL so long-idle in-memory sessions are evicted, if long-running-process memory growth becomes a concern.

This phase is not gated in this document — it will get its own goal/slices/gate when picked up, per `harness/patterns/phases.md`.
