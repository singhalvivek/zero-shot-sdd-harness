# Architecture

## System Overview

A single-user web app: a browser uploads one CSV to a FastAPI backend, which parses it into a pandas DataFrame held in server memory for the life of the session. Each chat question the user types triggers a LangGraph reasoning loop that writes pandas code against that DataFrame, executes it in a restricted in-process sandbox, inspects/critiques the result, retries on failure or low confidence (bounded), and finally composes a plain-language answer via the LLM. The Next.js frontend renders an upload step and a chat panel; it never sees the generated code, only the final answer text.

## Component Map

```
Browser (Next.js chat UI)
    │  1. POST /uploads (multipart CSV)
    ▼
FastAPI app (src/api)
    │  parses CSV → pandas DataFrame
    ▼
Session Store (src/session/store.py, in-memory dict)
    │  session_id → {df, filename, columns, messages[]}
    │
    │  2. POST /sessions/{id}/messages {question}
    ▼
LangGraph runner (src/graph/runner.py)
    │  loads session context, invokes graph
    ▼
Analysis Graph (src/graph/agent.py)
    │  write_code ──► execute_code ──► critique ──┬─► compose_answer ──► finalize
    │       ▲                                      │
    │       └──────────────(retry, bounded)────────┘
    │
    ├──► Sandbox (src/analysis/sandbox.py) — restricted exec() of LLM-written pandas code
    └──► LLM Client (src/llm/client.py) — Anthropic Claude, per-node model selection
    │
    ▼
Anthropic API (external)
```

## Layers

| Layer | Responsibility |
|-------|----------------|
| API (`src/api`) | HTTP surface: CSV upload, chat message endpoint, session lookup, error envelope |
| Session (`src/session`) | Holds the one in-memory session per `session_id`: the parsed DataFrame, schema summary, and chat message history |
| Agent graph (`src/graph`) | The write→execute→critique→retry→answer reasoning loop; owns `AgentState` |
| Analysis sandbox (`src/analysis`) | Restricted, bounded execution of LLM-generated pandas code against the session's DataFrame |
| LLM (`src/llm`) | Thin client over the Anthropic provider, model selection per call site |
| Persistence (`src/db`) | Durable log of each analysis run (question, answer, status) for observability only — not required for session continuity |

## Data Flow

1. Trigger: user uploads a CSV via the browser.
2. `POST /uploads` parses the file with `pandas.read_csv`, validates size/parseability, creates a new `session_id`, stores `{df, filename, columns, dtypes, messages: []}` in the in-memory session store, and returns `session_id` + a schema summary (filename, row count, columns) to the browser.
3. The browser holds `session_id` in React state and sends it with every chat call.
4. `POST /sessions/{session_id}/messages` with `{question}` looks up the session, appends the user turn to `messages`, and invokes the LangGraph runner with the question, the session's schema summary, and prior `messages`.
5. The graph's `write_code` node asks the LLM to produce pandas code (assigning to a `result` variable) using the question, schema, sample rows, and (on retry) the previous attempt's error/critique feedback.
6. `execute_code` runs that code in the sandbox against the session's DataFrame copy, bounded by a wall-clock timeout.
7. `critique` inspects the execution outcome (error, or `result` value vs. the question) and decides: confident / retry (bounded by `max_iterations`) / unanswerable.
8. `compose_answer` turns the confident result (or the unanswerable/give-up state) into one plain-language paragraph, embedding real numbers when confident.
9. The runner appends the assistant turn to the session's `messages`, logs an `AnalysisRunRow` (question, answer, status) for observability, and returns the answer.
10. Output: the browser renders the plain-language answer in the chat panel; on a fatal (non-user-facing) error, an error banner is shown instead.

## External Dependencies

| Dependency | Purpose | Failure Mode |
|------------|---------|--------------|
| Anthropic API (`AGENT_ANTHROPIC_API_KEY`) | Powers `write_code`, `critique`, `compose_answer` LLM calls | Any node's LLM call failure sets `state.error` and routes to `handle_error`; API surfaces a clear error to the UI, session/data are untouched so the user can retry the question |
| In-process pandas sandbox | Executes LLM-written analysis code | Execution errors (exceptions, timeout) are caught and fed back into the retry loop as feedback, never crash the request |
| SQLite (`AGENT_DATABASE_URL`) | Durable observability log of analysis runs | If the DB write fails, the answer is still returned to the user (log-and-continue, non-critical) |

## Stack

> This project's concrete technology choices. The generic, every-project rules — model-naming, DB driver, dev port, test environment — live in `harness/patterns/tech-stack.md`; this section is only what **this** project picked, extending the existing skeleton in place.

- **Language:** Python 3.11+ (backend, matches existing `pyproject.toml`); TypeScript (frontend, existing Next.js app).
- **Agent framework:** LangGraph (already a dependency; extends the existing `transform_text` skeleton graph into a multi-node write→execute→critique→retry→answer loop).
- **LLM provider + model:** Anthropic Claude via the existing `src/llm/client.py`.
  - `write_code` and `compose_answer` nodes: `claude-sonnet-4-6` (quality — code correctness and prose both matter).
  - `critique` node: `claude-haiku-4-5-20251001` (fast/cheap — a small structured verdict, called on every attempt so latency compounds).
  > **Assumed:** the fast-tier model for `critique` is configurable via a new `AGENT_LLM_MODEL_FAST` env var (default `claude-haiku-4-5-20251001`), added to `Settings` alongside the existing `llm_model`. Not specified at intake; chosen to keep the retry loop responsive.
- **Backend:** FastAPI (existing skeleton), extended with `POST /uploads` and `POST /sessions/{id}/messages`.
- **Database + ORM:** SQLite (existing skeleton default, `AGENT_DATABASE_URL=sqlite:///./data/agent.db`) + SQLAlchemy 2.0, used only as an observability log of analysis runs — never as the source of session state (session state is in-memory, per the product brief's "no persistence beyond the live session" requirement).
  > **Assumed:** SQLite is retained rather than switched to PostgreSQL — the brief explicitly frames this as a personal, single-user, local prototype tool with no stated DB preference, and the existing skeleton already defaults to SQLite. This does not violate the "no SQLite-substitute-for-Postgres" rule because no PostgreSQL preference was ever stated.
- **Frontend:** Next.js 15 + React 19 (existing skeleton), static-export served by FastAPI at `/app/` per the skeleton's existing convention.
- **Dependency management:** uv (Python, existing `pyproject.toml`) / pnpm (TypeScript, existing `frontend/`).
- **Session identification (no auth):** the backend mints a random `session_id` (UUID4) on upload and returns it in the response body. The frontend holds it only in React component state (never a cookie, never localStorage) — the session is scoped to the open browser tab and dies with it, matching "nothing needs to persist after the tab closes." Every chat request includes `session_id` in the JSON body.
- **Session storage:** a single process-global `dict[str, SessionData]` in `src/session/store.py`, guarded by a per-session `threading.Lock` to serialize concurrent requests against the same DataFrame. Not distributed, not persisted — acceptable because this is an explicitly single-user, single-process local tool. Session entries live for the process lifetime (no TTL in Phase 1; noted as a Phase 2 candidate).
- **Sandboxed code execution:** in-process restricted `exec()`, not a subprocess.
  > **Assumed / justified:** a subprocess-per-question sandbox (or a container/gVisor-style sandbox) would give stronger OS-level isolation, but the brief explicitly says "server-side sandboxed code execution against the CSV is fine" and frames this as an experimental/prototype tool with no data-residency lockdown. The complexity and latency cost of spawning and serializing DataFrames to a subprocess is disproportionate here. `src/analysis/sandbox.py` instead: (1) builds a restricted `__builtins__` allow-list (no `open`, `__import__`, `exec`, `eval`, `os`, `sys`), (2) exposes only `pd` and a `.copy()` of the session's DataFrame as `df`, (3) runs the `exec()` call inside a `concurrent.futures.ThreadPoolExecutor` with a wall-clock timeout (`AGENT_SANDBOX_TIMEOUT_S`, default `10`) so a runaway generated snippet can't hang a request, (4) captures stdout and the `result` variable, truncating large reprs before they reach the LLM. This is a prototype-grade sandbox, not a security boundary against a malicious CSV/question — acceptable per the stated constraints.

| Key library | Version | Purpose |
|-------------|---------|---------|
| pandas | already present (skeleton venv) | CSV parsing + generated analysis code execution |
| langgraph | >=0.1 (existing) | write→execute→critique→retry→answer graph |
| fastapi / python-multipart | existing / new | HTTP surface + multipart CSV upload |
| anthropic | existing | LLM calls |
| @playwright/test | existing (frontend node_modules) | E2E smoke test for the upload→chat journey |

**Avoid:** shelling out to `os.system`/`subprocess` for the analysis code (adds complexity the prototype doesn't need — see sandbox justification above); storing the DataFrame or chat history in the SQL database (violates "no persistence beyond the live session"); using the generic `RunRow`/`/runs` skeleton table for this capability's writes (kept untouched for the boilerplate's own tests; this capability uses its own `AnalysisRunRow`/`analysis_runs` table).

## Deployment Model

Local long-running process: `uv run python -m src` serves both the FastAPI API and the pre-built Next.js static export at `http://localhost:8001/app/`. No background workers, no queues — each chat request runs its graph invocation synchronously within the HTTP request/response cycle (acceptable given "latency is not a concern").
