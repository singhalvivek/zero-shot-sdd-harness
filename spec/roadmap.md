# Roadmap

---

## What This Agent Does

AI CAD Studio is a local, single-user web app that turns a plain-English description of a mechanical part into real parametric 3D geometry. The user types a description and picks a Gemini model; the backend has Gemini write CadQuery Python, safely executes it (self-repairing up to 3 times on failure), exports STL + STEP + the source, and renders the part in an interactive in-browser three.js viewer alongside the generated code, the repair log, and token/cost. The user then iterates — with natural-language follow-ups and by hand-editing the CadQuery code and re-running it — and browses a history of past parts and their modification chains.

## Who Uses It

A single maker / mechanical designer / engineer running the app locally, who wants to go from an idea to a printable/importable CAD file (STL for printing, STEP for CAD) without hand-writing CadQuery — and who wants full transparency (see the code, see the repairs, see the cost) and the ability to refine.

## Core Problem Being Solved

Writing parametric CAD code (CadQuery) by hand is slow and requires expertise; pure text-to-CAD tools are opaque black boxes. This app makes CAD generation fast **and** transparent + editable: you see and can hand-tune the exact code, watch it self-repair, and iterate in natural language — inspired by PartCAD and MakeIt3D.

## Success Criteria

- [ ] A plain-English prompt produces a valid part rendered in the 3D viewer, with downloadable STL + STEP, against the real Gemini key — first try.
- [ ] Generated code that fails to execute is self-repaired (≤3 attempts) and the repair log is shown; unsafe code is blocked before execution.
- [ ] The user can refine a part in natural language and by hand-editing code, each producing a new tracked version.
- [ ] Every part/version is persisted and browsable with a preview thumbnail and its modification chain.
- [ ] Token usage + estimated cost are shown per generation.

## What This Agent Does NOT Do (Out of Scope)

- No authentication / multi-user / cloud hosting (single-user localhost only).
- No assembly/multi-part modeling, no drawings, no simulation/FEA, no G-code/slicing.
- No delete/prune UI for history (manual folder cleanup only).
- No CAD kernels other than CadQuery/OpenCascade; no LLM providers other than Gemini.
- No server-side photorealistic rendering (thumbnails are client-captured from the viewer).

## Key Constraints

- **Windows platform:** the exec timeout MUST be process/thread-based (`multiprocessing` spawn + `terminate()`), never `signal.alarm`.
- **`cadquery-ocp` install risk:** the biggest risk; Python is pinned at scaffold to a version with importable, STL-capable wheels (a parallel probe confirms). Ship a real `requirements.txt` alongside `pyproject.toml`.
- Real Gemini key from `.env` (`AGENT_GEMINI_API_KEY`) for all tests — no stubs. Single-origin app at `:8001/app/`. Flat `src/` package (no nested package).
- Repair loop bounded at 3; exec runs in a restricted namespace with a wall-clock timeout.

## Phases of Development

> **Phase 1 is the smallest first-time-right user-testable win.** The full primary journey — prompt → model → generate → safe-exec + ≤3 repairs → export STL+STEP → render in the 3D viewer with code + repairs + cost shown — real end-to-end on one real example. Everything else (NL modify, code editor, history gallery, thumbnails) is a clearly-labelled non-functional stub, wired real in Phase 2.

### Phase 1 — Prompt → Part (generate, execute, self-repair, view)

- **Goal:** The user types a part description, picks a Gemini model, clicks Generate, and sees a real generated part render in the interactive 3D viewer — with the generated CadQuery code, the repair log (if any), and token/cost shown, and STL/STEP/code download buttons — proven end-to-end on one real example (e.g. a bracket or box) with the real Gemini key.
- **Independent slices (parallel build units):**
  - `db` (backend) — SQLAlchemy `PartRow` + `VersionRow` (full schema per [data.md](data.md)) + the Alembic migration. **deps: none.**
  - `pipeline` (backend) — `src/sandbox.py` (safety check + Windows-safe child-process exec + CadQuery export), `src/graph/{state,nodes,edges,agent,runner}.py` rewritten for the generate_part graph, `src/prompts/generate.md`, token/cost accounting, structlog observability. **deps: `db`** (persists versions).
  - `api` (backend) — `src/domain/run.py` (new request/response schemas), `src/api/runs.py` (`POST /runs`, `GET /runs/{id}`), `/artifacts` StaticFiles mount in `src/api/__init__.py`, `requirements.txt`; integration test `tests/phase1/`. **deps: `pipeline`.**
  - `frontend` (frontend) — `frontend/src/app/page.tsx` Studio: prompt + model selector + Generate (real), three.js STL viewer (real), collapsible syntax-highlighted code panel (real), repair-attempt panel (real), token/cost panel (real), STL/STEP/code download buttons (real), PLUS labelled stubs (follow-up modify box, edit-code toggle, history rail); Playwright smoke `frontend/tests/e2e/`. **deps: none** (contract-driven against [api.md](api.md)).
- **Key surfaces / files:** `db` → `src/db/models.py`, `alembic/versions/*`. `pipeline` → `src/sandbox.py`, `src/graph/*`, `src/prompts/generate.md`. `api` → `src/domain/run.py`, `src/api/runs.py`, `src/api/__init__.py`, `requirements.txt`, `tests/phase1/`. `frontend` → `frontend/src/app/page.tsx`, `frontend/src/components/*`, `frontend/src/lib/*`, `frontend/tests/e2e/*`. Disjoint paths; the backend chain `db → pipeline → api` serializes on true deps, `frontend` runs fully parallel.
- **Gate command:** `uv run alembic upgrade head` then `uv run pytest tests/phase1 -q` (real Gemini via `.env`, real SQLite) — the test must: (a) `POST /runs` with a real bracket/box prompt returns `status=completed`, (b) the STL file exists and parses as a mesh with >0 triangles, (c) the STEP file exists and is non-empty, (d) `token_usage.total_tokens > 0`, (e) code containing `import os` is rejected by the safety check without executing, (f) the repair loop is bounded at 3. Plus: app boots via `uv run python -m src` (no ImportError), `cd frontend && pnpm build` succeeds and `/app/` renders styled, and `npx playwright test` (frontend) drives the primary journey against the live app and asserts the viewer shows real geometry.
- **How the user tests it (handoff seed):** `cd frontend && pnpm build`, then `uv run alembic upgrade head`, then `uv run python -m src`; open `http://localhost:8001/app/`. Type "a 60x40x10mm rectangular bracket with two 5mm mounting holes", pick `gemini-2.5-flash`, click Generate. Expect: within a few seconds the part renders in the 3D viewer (rotate/zoom/pan), the code panel shows the CadQuery source, the cost panel shows tokens + $, and STL/STEP/Code download buttons work. If the first code failed, the repair panel shows what errored and what changed. The follow-up box, edit-code toggle, and history rail are visible but **labelled "Coming in Phase 2"** — those are stubs, not bugs.

### Phase 2 — Iterate + History (NL modify, edit-and-rerun, browsable history)

- **Goal:** Wire the three Phase-1 stubs into real features: refine a part with a natural-language follow-up (new version in the chain), hand-edit the CadQuery code and re-run it, and browse a gallery of past parts with thumbnails and their modification chains — each version reloadable into the viewer.
- **Capabilities delivered (3):** [modify_part](capabilities/modify_part.md), [edit_and_rerun](capabilities/edit_and_rerun.md), [browse_history](capabilities/browse_history.md).
- **Independent slices (parallel build units):**
  - `iterate-backend` (backend) — add `modify` + `edit` modes to the graph: conditional entry route, `modify` prompt framing with `previous_code`, `edit` mode skipping generate + repair, version-chain persistence (`parent_version_id`, `source`); `src/prompts/modify.md`. **deps: Phase 1.**
  - `parts-api` (backend) — `src/api/parts.py`: `POST /parts/{id}/modify`, `POST /parts/{id}/rerun`, `GET /parts`, `GET /parts/{id}`, `PUT /parts/{id}/versions/{n}/thumbnail`; register in `src/api/__init__.py`; integration tests `tests/phase2/`. **deps: `iterate-backend`.**
  - `iterate-frontend` (frontend) — wire the follow-up modify box (`POST modify`), the code editor (CodeMirror) + Re-run (`POST rerun`), the history rail gallery (`GET /parts` + thumbnails, `GET /parts/{id}` chain, version reload), and client thumbnail capture (`canvas.toDataURL()` → `PUT thumbnail`); extend Playwright E2E. **deps: none** (contract-driven).
- **Key surfaces / files:** `iterate-backend` → `src/graph/{state,nodes,edges,runner}.py`, `src/prompts/modify.md`. `parts-api` → `src/api/parts.py`, `src/api/__init__.py`, `tests/phase2/`. `iterate-frontend` → `frontend/src/app/page.tsx`, `frontend/src/components/{HistoryRail,CodeEditor,ModifyBox}.tsx`, `frontend/tests/e2e/*`. Disjoint paths; `parts-api` serializes on `iterate-backend`, frontend runs parallel.
- **Gate command:** `uv run alembic upgrade head` then `uv run pytest tests/phase2 -q` (real Gemini via `.env`) — must assert: (a) a NL follow-up on an existing part creates `version_number = parent+1` with `parent_version_id` set and geometry that differs from the parent for a dimension-changing prompt, (b) an edited-code re-run creates an `edit`-source version with no LLM call and rejects `import os`, (c) `GET /parts` lists the created parts newest-first and `GET /parts/{id}` returns the ordered version chain, (d) a `PUT thumbnail` persists and is served back. Plus `npx playwright test` drives modify + edit + history in the browser.
- **How the user tests it (handoff seed):** With the app running, generate a part (Phase 1). Then type "make the mounting holes 6mm" in the now-active follow-up box → a new version renders and the code updates. Toggle "Edit code", change a dimension constant, click Re-run → a new version renders with no cost charged. Open the History rail → see tiles (with thumbnails) for every part; click one → see its version chain; click a past version → it reloads into the viewer and code panel. Everything is real now — no stubs remain.

<!-- Agentic Stack Upgrade / Complete Agentic System phases are NOT added: the generate→check→exec→repair graph is fully specified and wired in Phase 1; Phase 2 completes every capability. No trailing production phase is required for this local single-user tool beyond a README/handoff pass folded into Phase 2's gate. -->
