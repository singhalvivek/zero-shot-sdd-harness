# AI CAD Studio

> **All commands run from the repo root** (this directory — there is no subdirectory to `cd` into). The one exception is the two `frontend/` build/test commands, which explicitly `cd frontend` as noted.

Type a plain-English description of a mechanical part → Google **Gemini** writes **CadQuery** Python → the backend safely executes it into real parametric 3D geometry (with up to 3 self-repairs on failure) → exports **STL + STEP** → renders the part in an interactive in-browser **three.js** viewer, alongside the generated code, the repair log, and the token/cost. Local, single-user. Inspired by PartCAD and MakeIt3D.

Stack: Python 3.12 · FastAPI · LangGraph · SQLite · CadQuery (OpenCascade) · Next.js 15 + three.js. Single-origin: the built frontend is served by FastAPI at `/app`.

---

## Prerequisites

- **Python 3.12** — pinned via `.python-version` (`3.12.10`). CadQuery's `cadquery-ocp` (OpenCascade) wheels require 3.11/3.12; **3.13 is not supported**. `uv` reads the pin automatically.
- [`uv`](https://docs.astral.sh/uv/) for Python deps, and **`pnpm`** + Node ≥ 20 for the frontend.
- A **Google Gemini API key** (Developer API, starts with `AIza…`) from https://aistudio.google.com/apikey.

## Setup

```bash
# from the repo root
cp .env.example .env
# edit .env and set:  AGENT_GEMINI_API_KEY=<your Gemini key>

uv sync                 # installs the backend + CAD stack (downloads OpenCascade — large, first time only)
```

## Run

```bash
# from the repo root
cd frontend && pnpm install && pnpm build && cd ..   # builds the SPA into frontend/out/
uv run alembic upgrade head                          # creates the SQLite schema (runs, parts, versions)
uv run alembic current                               # verify — must print a revision hash, not blank
uv run python -m src                                 # starts the server on http://localhost:8001
```

Then open **http://localhost:8001/app/**.

| URL | What |
|-----|------|
| `http://localhost:8001/app/` | **AI CAD Studio UI** |
| `http://localhost:8001/health` | Health check (`{"data":{"status":"ok"},"error":null}`) |
| `http://localhost:8001/artifacts/...` | Served STL / STEP / code files |

## Use it (Phase 1)

1. Type a part description, e.g. **"a 60x40x10mm rectangular bracket with two 5mm mounting holes"**.
2. Pick a model: **Flash 3.5** (higher quality, default) or **Flash Lite** (fastest/cheapest).
3. Click **Generate**. In a few seconds the part renders in the 3D viewer (rotate / zoom / pan); the code panel shows the CadQuery source; the token/cost panel shows usage; download **STL / STEP / Code**. If the first attempt failed to execute, the repair panel shows what errored and what changed (up to 3 tries).

> **Models:** this build uses `gemini-3.5-flash` (quality/default) and `gemini-3.1-flash-lite` (fast). Pro-tier models (`gemini-*-pro`) require a **billing-enabled** Gemini key — free-tier keys return quota errors — so the "quality" slot is currently the strongest available flash model. Add a pro id to `ALLOWED_MODEL_IDS` in `src/config/settings.py` once a billing-enabled key is in `.env`.

**Coming in Phase 2** (currently visible but clearly labelled stubs — not bugs): natural-language "refine this part" follow-ups, an in-browser CadQuery code editor with re-run, and a browsable history gallery of past parts with thumbnails and their modification chains.

## Tests

```bash
# from the repo root — these hit the REAL Gemini API using the key in .env
uv run pytest tests/phase1 -q      # the Phase 1 gate (generate -> exec -> export, real Gemini)
uv run pytest -q                   # full suite (unit + sandbox + integration + phase1)

# frontend golden-path E2E (server must be running per "Run" above)
cd frontend && npx playwright test
```

## Where things live

- `src/graph/` — the generate → safety-check → execute → repair(≤3) → export **LangGraph** pipeline (`spec/agent.md`).
- `src/sandbox.py` — the safety-critical piece: static safety check (rejects `os.`, `open(`, `subprocess`, … via AST + regex) + a **Windows-safe** (`multiprocessing` spawn + `terminate()` timeout) restricted-namespace executor that exports STL/STEP inside the child process.
- `src/llm/providers/gemini.py` — per-request Gemini model, token/cost accounting, 429 backoff.
- `generated_code/` and `artifacts/` — versioned CadQuery source, STL/STEP exports, and preview images (gitignored; created at runtime).
- Full design in `spec/` (roadmap, architecture, agent graph, data, api, ui, capabilities).

Local, single-user, localhost-bound — no authentication, no cloud.
