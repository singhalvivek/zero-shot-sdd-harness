# Personal Data Analysis Agent

Upload a CSV, ask questions in plain English, get streamed plain-language answers with the key numbers called out. A LangGraph agent plans an analysis, writes pandas, and **runs it in a local sandbox** — your raw data rows never leave the machine. Only column names, dtypes, and aggregate results are ever sent to the LLM (Gemini).

> **All commands below run from the repository root** (where `pyproject.toml` and `alembic.ini` live). There is no subdirectory to `cd` into for the backend.
> **All Python commands use the `uv run` prefix.** Bare `python`/`pytest`/`alembic` will fail unless you activate the venv manually.

## Stack

Python · FastAPI · LangGraph · SQLite · pandas · Gemini · Next.js (static export served at `/app/`).

## Prerequisites

- [uv](https://docs.astral.sh/uv/) (Python package/venv manager)
- [pnpm](https://pnpm.io/) (frontend)
- A Gemini API key

## Setup

1. Copy the env template and fill in your Gemini key:
   ```bash
   cp .env.example .env
   # edit .env: set AGENT_GEMINI_API_KEY=...  (AGENT_LLM_PROVIDER=gemini is already set)
   ```
2. Install backend dependencies:
   ```bash
   uv sync --extra dev
   ```
3. Create the database (SQLite under `data/`):
   ```bash
   uv run alembic upgrade head
   uv run alembic current   # must print a revision hash, e.g. 4f6a8a12f9c1 (head) — blank means it failed
   ```
4. Build the frontend (static export served by the backend at `/app/`):
   ```bash
   cd frontend && pnpm install && pnpm build && cd ..
   ```

## Run

```bash
uv run python -m src
```
Then open **http://localhost:8001/app/** in your browser.

- Upload a CSV (e.g. one with `dept,salary` columns).
- Type a question: *"what is the average salary by department?"*
- Press **Ask** — the answer streams back in plain language with the numbers called out.

## Test

Runs against the **real Gemini API** using the key in `.env` (no offline stub):

```bash
uv run pytest                                  # backend unit + integration + e2e (real Gemini)
cd frontend && pnpm exec playwright test       # frontend E2E against the live app at :8001/app/
```

## What works today (Phases 1–3 — complete)

Every capability is real. Nothing is stubbed.

- **Upload & ask (P1):** upload a CSV → ask a natural-language question → streamed plain-language answer with the key numbers called out, produced by the real plan → write_code → execute (local pandas sandbox) → refine → answer loop.
- **Clarifying-question gate (P2):** on a genuinely ambiguous question the agent pauses and asks a clarifying question instead of guessing; you answer with a normal follow-up.
- **Follow-up suggestion chips (P2):** 2–3 smart, clickable follow-up questions after each answer.
- **Live token-usage badge (P2):** real per-query prompt/completion token counts on each answer.
- **Audit-log viewer (P2):** an Audit tab listing past queries, answers, token counts, status, and timestamps (newest first).
- **Multi-file analysis (P3):** upload several files into one session and ask questions that join/compare across them.
- **Excel support (P3):** upload `.xlsx`/`.xls` files alongside CSV.
- **Persistent session switcher (P3):** list past sessions and resume one — with its files and conversation history — across app restarts.

## Privacy guarantee

Raw data rows never leave your machine. The generated pandas runs in an isolated local subprocess; only column names, dtypes, row counts, and computed **aggregate** results are ever placed in a prompt to Gemini.
