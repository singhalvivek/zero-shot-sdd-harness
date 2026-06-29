# Architecture

---

## System Overview

A single-user local web application. The Next.js frontend (served at `:8001/app/`) lets the user upload tabular files and ask natural-language questions. The FastAPI backend stores uploaded files locally, runs a LangGraph agent that plans an analysis, writes pandas code, executes it in an isolated local subprocess sandbox against the loaded dataframes, refines on error, and streams a plain-language answer back to the browser. Only schema and aggregate results are ever sent to the Gemini LLM; raw rows stay on the machine. Every query/answer is persisted to a SQLite audit log.

## Component Map

```
[Next.js UI  :8001/app/]
        │  upload file / ask (SSE stream)
        ▼
[FastAPI  :8001]  ──►  [LangGraph agent: plan→write_code→execute→refine→answer]
        │                        │ schema + aggregate results only
        │                        ▼
        │                 [Gemini LLM]
        │                        │ pandas code
        │                        ▼
        │              [Local pandas sandbox (subprocess)]  ◄── raw rows (local only)
        ▼
[SQLite: datasets / sessions / messages / audit_log]
```

## Layers

| Layer | Responsibility |
|-------|----------------|
| API (FastAPI) | Upload handling, session routing, SSE streaming of answers |
| Agent (LangGraph) | Plan → write code → execute → refine → answer loop; conversation memory |
| Sandbox (subprocess) | Run generated pandas against loaded dataframes; capture result/stdout/error |
| Storage (SQLite + SQLAlchemy) | Datasets metadata, sessions, message history, audit log |
| LLM (Gemini provider) | Code generation + answer phrasing; receives schema/aggregates only |

## Data Flow

1. Trigger: user uploads a file (`POST /datasets`) → stored under `data/uploads/`, schema profiled, `dataset` row created.
2. User asks a question (`POST /sessions/{id}/ask`) → graph runs with the file schema + conversation history in state.
3. `plan` proposes a strategy; `write_code` emits pandas; `execute` runs it in the sandbox; on error `refine` rewrites (bounded retries).
4. `answer` turns the aggregate result into streamed plain language; query+answer+tokens persisted to `audit_log`.
5. Output: streamed plain-language answer (SSE) shown in the UI; numbers called out.

## External Dependencies

| Dependency | Purpose | Failure Mode |
|------------|---------|--------------|
| Gemini API | Plan, code generation, answer phrasing | Retry w/ backoff; surface error to user after retries exhausted |
| Local subprocess (pandas) | Execute generated analysis code | Captured error fed back to `refine`; after max refines, graceful error answer |

## Stack

> Concrete choices for THIS project. Generic rules live in `harness/patterns/tech-stack.md`.

- **Language:** Python 3.12+ (backend), TypeScript (frontend)
- **Agent framework:** LangGraph
- **LLM provider + model:** Gemini (`AGENT_LLM_PROVIDER=gemini`); model from `AGENT_LLM_MODEL`, provider default `gemini-3.1-pro`
- **Backend:** FastAPI, served via `uv run python -m src` at `:8001`
- **Database + ORM:** SQLite + SQLAlchemy 2.0 + Alembic (SQLite is the production DB here; tests use SQLite too)
- **Frontend:** Next.js 15 + React 19 (static export, served at `:8001/app/`)
- **Dependency management:** uv + pyproject.toml (Python); pnpm (frontend)

| Key library | Version | Purpose |
|-------------|---------|---------|
| langgraph | latest | Agent graph + state |
| google-genai | latest (already a dep) | Gemini provider |
| pandas | latest | Local data analysis |
| openpyxl | latest | Excel reading (Phase 3) |
| sqlalchemy | 2.x | ORM |
| alembic | latest | Migrations |
| playwright | latest | Frontend E2E |

**Avoid:** sending raw dataframe rows to the LLM (privacy violation); `eval`/`exec` of LLM code in the main process (must be subprocess-isolated); any cloud data store or external export.

## Deployment Model

Long-running local service started with `uv run python -m src`; FastAPI serves both the API and the static Next.js export. Single user, single machine. Uploaded files and the SQLite DB live under `data/`.
