# Architecture

---

## System Overview

AI CAD Studio is a **local, single-user web app**. A browser SPA sends a plain-English part description + a model choice to a FastAPI backend. A LangGraph pipeline asks Google Gemini to write CadQuery Python, statically safety-checks it, executes it in a sandboxed child process (Windows-safe timeout), self-repairs on failure (≤3), exports STL + STEP + the source, and returns URLs the browser's three.js viewer loads. Everything is versioned to SQLite + the filesystem so parts can be iterated (NL follow-ups, hand-edited code) and browsed. It extends the harness skeleton in place — the `transform_text` capability slot becomes `generate_part`.

## Component Map

```
Browser SPA (Next.js + three.js)
    │  POST /runs {prompt, model_id}         GET /artifacts/**  (STL/STEP/code/png)
    ▼                                              ▲
FastAPI (src/api)  ──►  Runner (src/graph/runner) ─┼─► SQLite (runs, parts, versions)
    │                        │                     │
    │                        ▼                     └─► filesystem (generated_code/, artifacts/)
    │            LangGraph pipeline (src/graph)
    │              generate_code ─► Gemini API (google-genai)
    │              static_safety_check ─► src/sandbox.py
    │              execute_cadquery ─► child process: CadQuery/OCC exec + export
    │              repair_on_error ─► Gemini API
    │              export_model ─► filesystem
    ▼
Observability: structlog JSON (always) + LangSmith (optional, env-gated)
```

## Layers

| Layer | Responsibility |
|-------|----------------|
| Frontend (`frontend/`) | Studio SPA: prompt, model selector, three.js viewer, code/repair/cost panels, downloads; Phase-2 stubs |
| API (`src/api`) | `POST /runs`, `GET /runs/{id}`, Phase-2 `/parts/*`, `/artifacts` static mount, `/health`; `{data,error}` envelope |
| Runner (`src/graph/runner.py`) | Creates `RunRow`, seeds `AgentState`, invokes the graph, commits `parts`/`versions` + result JSON |
| Agent graph (`src/graph`) | The generate→check→exec→repair→export state machine (see [agent.md](agent.md)) |
| Sandbox (`src/sandbox.py`) | Static safety check + restricted-namespace child-process exec with Windows-safe timeout + CadQuery export |
| LLM (`src/llm`) | `GeminiProvider` (per-run model), token/cost accounting |
| Data (`src/db`) | SQLAlchemy models + Alembic migrations (SQLite) |

## Data Flow

1. **Trigger:** user submits `{prompt, model_id}` → `POST /runs`.
2. Runner creates a `RunRow` + a new `part_id`, seeds `AgentState` (mode=`generate`).
3. `generate_code` → Gemini writes CadQuery (fences stripped); token/cost recorded.
4. `static_safety_check` rejects forbidden calls; violation → fail.
5. `execute_cadquery` runs the code in a sandboxed child process (timeout); on success exports STL+STEP inside that process; on error/timeout → `repair_on_error` (≤3) which re-checks then re-executes.
6. `export_model` writes the versioned `.py`; `finalize` sets status; runner commits `parts` + `versions v1` and the result JSON.
7. **Output:** response with `generated_code`, `stl_url`/`step_url`/`code_url`, `repair_attempts`, `token_usage`, `cost_usd`; the SPA loads the STL into three.js and renders the panels.

## External Dependencies

| Dependency | Purpose | Failure Mode |
|------------|---------|--------------|
| Google Gemini API (`google-genai`) | Generate & repair CadQuery code | 502 surfaced; run fails (no offline fallback) |
| CadQuery + `cadquery-ocp` (OpenCascade) | Execute code → STL/STEP export (in-process, sandboxed) | exec error → repair loop; import failure = install/scaffold blocker |
| SQLite | Persist runs/parts/versions | 500 |
| Filesystem | Store code + STL/STEP/preview | fatal → run fails |

## Stack

- **Language:** Python **3.12** — pinned at scaffold via `.python-version` (3.12.10). **Verified at scaffold:** `cadquery==2.8.0` + `cadquery-ocp==7.9.3.1.1` import and export both STL and STEP in the project venv on this Windows machine. Frontend TypeScript.
- **Agent framework:** LangGraph (replaces the skeleton's single-node graph in place).
- **LLM provider + model:** Google Gemini via `google-genai`, per-request `model_id` ∈ {`gemini-3.5-flash`, `gemini-3.1-flash-lite`}. Key `AGENT_GEMINI_API_KEY` (pydantic settings, `env_prefix=AGENT_`) passed explicitly to `genai.Client(api_key=...)`.
  > **Model-id verification — DONE at scaffold (2026-07-14, live API).** The two selectable models are **`gemini-3.5-flash`** — the newest full (non-lite) flash model and the **highest-reasoning model available on this key** (default, the "quality" slot) — and **`gemini-3.1-flash-lite`** (the fastest/cheapest lite tier). Both confirmed to `generateContent` against the live Gemini API with the `.env` key. Substituted for the intake-requested `gemini-2.5-flash`/`gemini-2.5-pro`, which are unusable with this key: `gemini-2.5-flash`/`-flash-lite` → 404 "no longer available to new users". **No pro-tier model is available on this free-tier key:** every `*-pro` id (`gemini-2.5-pro`, `gemini-pro-latest`, `gemini-3-pro-preview`, `gemini-3.1-pro-preview`) returns 429 RESOURCE_EXHAUSTED with `PerDay`+`FreeTier` quota metrics even when probed 35s apart (a hard zero-quota cap, not a per-minute rate limit). So the "quality" slot is the strongest available flash for now; pro-tier can be enabled later by supplying a billing-enabled key (add its id to the allowed set). The runner constructs `GeminiProvider` per-request with the chosen `model_id`; the provider retries once on a transient 429 with backoff.
- **Backend:** FastAPI + uvicorn on port **8001**; health at `/health`; run via `uv run python -m src`.
- **Database + ORM:** SQLite + SQLAlchemy 2.0 + Alembic. Flat `src/` package (imports `from graph.runner import run_agent`, `from api import runs`; `pythonpath=["src"]`) — **no nested package**.
- **Frontend:** Next.js 15 (App Router, static export) + React 19 + Tailwind + three.js; built to `frontend/out/`, mounted at `/app`, served single-origin at `:8001/app/`.
- **Dependency management:** uv + `pyproject.toml` (source of truth). **Additionally produce a real `requirements.txt`** (user-requested) pinning the runtime deps — `cadquery`, `cadquery-ocp`, `google-genai`, plus fastapi/uvicorn/pydantic/sqlalchemy/alembic/langgraph/structlog — so the CAD stack can be installed with plain `pip` on Windows if uv resolution stalls.

| Key library | Version | Purpose |
|-------------|---------|---------|
| cadquery | latest compatible w/ pinned Python | Parametric CAD, STL+STEP export via `cadquery.exporters` |
| cadquery-ocp | matched to cadquery | OpenCascade bindings (the main Windows install risk) |
| google-genai | >=2.9.0 (in pyproject) | Gemini SDK |
| langgraph | >=0.1 | Pipeline graph |
| fastapi / uvicorn | >=0.115 / >=0.30 | API + server |
| sqlalchemy / alembic | >=2.0 / >=1.13 | ORM + migrations |
| structlog | >=24.1 | Structured logging |
| three (frontend) | latest | 3D viewer (STLLoader + OrbitControls) |
| react-syntax-highlighter / @uiw/react-codemirror (frontend) | latest | Code display (P1) / editor (P2) |
| @playwright/test (frontend dev) | latest | E2E smoke |

**Avoid:** `signal.alarm` for the exec timeout (Unix-only — this is Windows); server-side headless-GL thumbnail rendering (heavy Windows dep — thumbnails are client-captured); LLM tool-calling for the pipeline (edges are deterministic); a nested `src/agent/` package (skeleton uses flat `src/`).

## Sandbox Design (the safety-critical piece)

`src/sandbox.py`:
- **`static_safety_check(code) -> str | None`** — reject `open(`, `os.`, `sys.`, `subprocess`, `requests`, `socket`, `shutil`, `urllib`, `__import__`, `eval(`, `exec(`, `Path(`, `os.system`, file/network tokens. AST-walk in addition to substring match to catch obfuscation; returns the violation reason or None. Runs before **every** execution (generated, repaired, and user-edited).
- **`run_and_export(code, part_id, version, formats, timeout) -> dict`** — spawns a **child process** (`multiprocessing` with `spawn` start method — Windows-safe). In the child: build a restricted `__builtins__` (no `open`/`__import__` except a whitelist of `cadquery`, `math`), `exec` the code, fetch `result` (must be a CadQuery Workplane/Shape), and export STL+STEP via `cadquery.exporters.export(...)` to the versioned paths. Parent `join(timeout)`; if still alive → `terminate()` and return `{ok: False, error: "execution timed out after Ns"}`. Returns `{ok, error, stl_path, step_path}` (all picklable) — the Workplane never crosses the process boundary, which is why exec+export happen together in the child.

## Filesystem & Persistence

See [data.md](data.md) — SQLite tables `runs`/`parts`/`versions`; `generated_code/part_<id>/v<n>.py` (browsable) + `artifacts/{code,exports,previews}/...` (URL-served). `.gitignore` excludes `generated_code/`, `artifacts/`, `data/`.

## Deployment Model

Local long-running process: `cd frontend && pnpm build` then `uv run python -m src` → open `http://localhost:8001/app/`. No cloud, no auth, localhost-bound.
