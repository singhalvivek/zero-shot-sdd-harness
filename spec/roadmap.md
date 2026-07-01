# Roadmap

---

## What This Agent Does

A personal, browser-based data analysis agent. The user uploads one or more tabular data files (CSV/Excel) and then asks many natural-language questions about them in a single, continuous session. The agent plans an analysis strategy, writes and runs pandas code locally in a sandbox, iterates until the result is correct, and returns a streamed plain-language answer with the key numbers called out. Files and conversation history stay loaded across the session, so the user can ask follow-ups ("now break that down by region") and compare across files. Raw data rows never leave the machine — only schemas and aggregate results are sent to the LLM.

## Who Uses It

A single power user (the operator running it on their own machine) who works with small tabular datasets and wants fast, conversational answers without writing SQL or pandas by hand. They use it frequently and value trustworthy, exact numbers over speed.

## Core Problem Being Solved

Replaces the manual loop of opening a spreadsheet or a Jupyter notebook and hand-writing pandas/filters for every ad-hoc question. The agent makes data exploration conversational while keeping raw data on the local machine.

## Success Criteria

- [ ] User uploads a CSV and asks a natural-language question; the agent returns a correct plain-language answer with the key number(s) called out, streamed token-by-token.
- [ ] The agent answers by executing real pandas code locally — the answer's numbers match a hand-computed pandas result on the same file.
- [ ] No raw data row is ever sent to the LLM — only schema, dtypes, `df.head()`, and aggregate results appear in any prompt (verifiable in logs).
- [ ] Follow-up questions in the same session reuse prior conversation context ("break that down" works without re-stating the subject).
- [ ] Every query and its answer are persisted to an audit log with a timestamp and token counts.

## What This Agent Does NOT Do (Out of Scope)

- No external integrations, data sources, or exports (no DB connectors, no Google Sheets, no PDF/email output).
- No multi-user accounts, auth, or sharing — single local user.
- No charts/visualizations — answers are plain language with numbers.
- No editing/transforming the source files; read-only analysis.
- No exposing or letting the user edit the generated pandas code (code is hidden).
- No large datasets — small files only (a few MB).

## Key Constraints

- **Privacy:** raw data rows must stay on the local machine; only schema + aggregate results may be sent to the LLM. This is a hard guarantee, not a preference.
- **Trust bar:** production quality — numbers must be correct; the agent iterates until execution succeeds.
- **Latency:** flexible (small files, single user).
- **Stack:** Python + FastAPI + LangGraph + SQLite, pandas for analysis, Gemini LLM, Next.js frontend (see `architecture.md` → `## Stack`).
- **Sandbox:** generated pandas runs in an isolated local subprocess with the dataframes loaded; only captured results return to the graph.

## Phases of Development

> **Phase 1 is the smallest first-time-right user-testable win.** Real on the single-CSV path; everything else is a clearly-labelled non-functional stub so the user sees the vision.

### Phase 1 — Upload-one CSV, ask-one question, streamed answer

- **Goal:** User uploads ONE CSV, asks ONE natural-language question, and gets a streamed plain-language answer with key numbers called out — produced by the real plan → write-code → execute-pandas → refine → answer LangGraph loop running pandas locally in a sandbox (raw rows stay local; only schema + aggregate results reach Gemini). The query+answer+token-usage row is persisted to the audit log; token usage is captured server-side (display can be a labelled stub).
- **Independent slices (parallel build units):**
  - `db-migration` (backend) — Alembic migration for `dataset`, `session`, `message`, `audit_log` tables and the SQLAlchemy models. Deps: none.
  - `sandbox-exec` (backend) — the local pandas sandbox runner (`src/analysis/sandbox.py`) + dataframe loader; pure module with its own unit tests. Deps: none.
  - `agent-graph` (backend) — replace the `transform_text` slot with the `plan → write_code → execute → refine → answer` nodes, state, edges, prompts, and the streaming runner. Deps: `sandbox-exec` (calls it), `db-migration` (writes audit_log). Serialized after those two.
  - `api-routes` (backend) — `POST /datasets` (upload), `POST /sessions/{id}/ask` (SSE streamed answer), `GET /sessions/{id}` endpoints wiring the runner. Deps: `agent-graph`.
  - `frontend` (frontend) — real upload + question box + streamed-answer panel for the single-CSV path; PLUS clearly-labelled non-functional stubs (multi-file join, Excel upload, clarifying-question gate, follow-up suggestions, audit-log viewer, token-usage display, persistent sessions). Deps: none (codes against the API contract in `api.md`).
- **Key surfaces / files:** `alembic/versions/*`, `src/db/models.py` (backend: db-migration); `src/analysis/sandbox.py`, `src/analysis/loader.py` (backend: sandbox-exec); `src/graph/state.py`, `src/graph/nodes.py`, `src/graph/edges.py`, `src/graph/agent.py`, `src/graph/runner.py`, `src/prompts/*.md` (backend: agent-graph); `src/api/datasets.py`, `src/api/sessions.py` (backend: api-routes); `frontend/src/app/page.tsx`, `frontend/src/components/*`, `frontend/tests/e2e/*` (frontend).
- **Gate command:** `uv run alembic upgrade head && uv run pytest && uv run --directory frontend playwright test` (runs against real Gemini via `.env` keys and the production SQLite DB).
- **How the user tests it (handoff seed):** Run `uv run python -m src`, open `http://localhost:8001/app/`. Upload the sample CSV, type a question (e.g. "what is the average salary by department?"), press Ask. Expect a streamed plain-language answer with the numbers called out within a few seconds. REAL: upload one CSV, ask, streamed answer. LABELLED STUBS (greyed/"Coming soon" badges, must not look broken): the second-file upload, Excel toggle, follow-up-suggestion chips, token-usage figure, the audit-log tab, persistent-session switcher.

### Phase 2 — Conversational polish: clarify, suggest, show usage, audit log

- **Goal:** The agent asks a clarifying question when a query is ambiguous, suggests 2–3 follow-ups after each answer, displays real per-query token usage, and exposes a working audit-log viewer of past queries/answers.
- **Independent slices (parallel build units):**
  - `clarify-gate` (backend) — a `triage` node + conditional edge that detects ambiguity and pauses with a clarifying question (human-in-the-loop checkpoint) before planning. Deps: none (extends graph).
  - `suggestions` (backend) — the `answer` node also emits 2–3 follow-up question suggestions; surfaced in the ask response. Deps: none.
  - `audit-api` (backend) — `GET /audit` returning persisted query/answer/token rows. Deps: none (reads existing `audit_log`).
  - `frontend-wire` (frontend) — wire the clarifying-question prompt, follow-up chips, token-usage number, and audit-log tab to real data; remove their stub labels. Deps: `clarify-gate`, `suggestions`, `audit-api` (consumes their contracts).
- **Key surfaces / files:** `src/graph/nodes.py`, `src/graph/edges.py`, `src/prompts/triage.md`, `src/prompts/answer.md` (backend); `src/api/audit.py` (backend); `frontend/src/components/*`, `frontend/tests/e2e/*` (frontend).
- **Gate command:** `uv run alembic upgrade head && uv run pytest && uv run --directory frontend playwright test`
- **How the user tests it:** Ask a deliberately ambiguous question ("which is the best one?") and confirm the agent asks a clarifying question before answering; answer it and get the result. After any answer, see 2–3 clickable follow-up chips, the real token count, and an Audit tab listing prior queries with timestamps.

### Phase 3 — Multi-file & Excel & persistent sessions

- **Goal:** Upload multiple files (CSV + Excel), ask questions that join/compare across them, and resume a prior session across days.
- **Independent slices (parallel build units):**
  - `excel-loader` (backend) — extend the loader to read `.xlsx` (sheet-aware) alongside CSV. Deps: none.
  - `multifile-graph` (backend) — load multiple named dataframes into the sandbox namespace and teach the planner/code-writer to reference them by name for joins/compares. Deps: `excel-loader` (uses loaded frames).
  - `session-persistence` (backend) — `GET /sessions` list + resume endpoint; sessions and their dataset bindings survive restarts. Deps: none.
  - `frontend-multifile` (frontend) — multi-file upload list, Excel acceptance, and a session switcher; remove their stub labels. Deps: the three backend slices.
- **Key surfaces / files:** `src/analysis/loader.py`, `src/graph/nodes.py`, `src/prompts/*.md`, `src/api/sessions.py` (backend); `frontend/src/components/*`, `frontend/tests/e2e/*` (frontend).
- **Gate command:** `uv run alembic upgrade head && uv run pytest && uv run --directory frontend playwright test`
- **How the user tests it:** Upload two files (one CSV, one Excel), ask a question that compares them ("compare avg order value between the two regions files"); get a correct joined answer. Close and reopen the app, pick the prior session from the switcher, and continue asking with prior files still loaded.
