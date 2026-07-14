# UI

---

## UI Type

Single-page web app — Next.js 15 (App Router, static export) + React 19 + Tailwind, served at `http://localhost:8001/app/`. One screen ("Studio") with a 3D viewer at the center. Built with `pnpm build` → `frontend/out/` → mounted at `/app` by FastAPI.

## Views / Screens

### Screen: Studio (the only screen)

**Purpose:** Type a description, pick a model, generate a part, see it render in 3D alongside its code, repairs and cost; then iterate.

**Layout:** three-column responsive:
- **Left — History rail** *(Phase 2 real; Phase 1 stub)*
- **Center — Prompt + 3D viewer**
- **Right — Code / repairs / cost panel**

**Key elements & phase status:**

| Element | Phase 1 | Detail |
|---------|---------|--------|
| Prompt textarea | REAL | Plain-English part description |
| Model selector (`gemini-2.5-flash` / `gemini-2.5-pro`) | REAL | Dropdown; default flash |
| Generate button | REAL | `POST /runs`; shows loading + "generating / executing / repairing (n/3)" status |
| 3D viewer | REAL | three.js `STLLoader` + `OrbitControls` — rotate / zoom / pan; loads `stl_url` |
| Code panel (collapsible, syntax-highlighted) | REAL | Read-only in Phase 1; shows `generated_code` |
| Repair-attempts panel | REAL | Accordion: per attempt shows the error + change summary (up to 3) |
| Token/cost panel | REAL | `token_usage.total_tokens` + `cost_usd` |
| Download buttons (STL / STEP / Code) | REAL | Anchor `download` to `stl_url`/`step_url`/`code_url` |
| Safety/error banner | REAL | Shows `safety_violation` or failure reason distinctly from network errors |
| **Follow-up modify box** ("Refine this part…") | **STUB** — visible, disabled, labelled "Coming in Phase 2" | Wired by `modify_part` |
| **"Edit code & re-run" toggle** in the code panel | **STUB** — labelled | Wired by `edit_and_rerun` (CodeMirror editor) |
| **History rail** (gallery of past parts + thumbnails) | **STUB** — labelled placeholder tiles | Wired by `browse_history` |

**Actions available (Phase 1):** enter prompt → select model → Generate → orbit the part → expand/collapse code → expand repair log → download STL/STEP/code.

**Phase 2 additions (wire the stubs):**
- Follow-up box → `POST /parts/{id}/modify`, appends a version, re-renders.
- Code panel edit toggle → CodeMirror editor + "Re-run" → `POST /parts/{id}/rerun`.
- History rail → `GET /parts` gallery with thumbnails; click → `GET /parts/{id}` chain; select a version → reload viewer + code; capture `canvas.toDataURL()` → `PUT .../thumbnail`.

## Error States

- **Network error** (server down): red banner "Network error — is the server running?".
- **Pipeline failure** (`status:"failed"`): amber panel showing the reason — safety violation ("blocked: code used `import os`"), repair-exhausted ("could not produce valid geometry after 3 attempts", with the repair log), or export error.
- **Loading:** the Generate button shows staged status; the viewer shows a spinner/skeleton; panels show placeholders until data arrives.
- **Stubs:** every non-functional element carries a visible "Coming in Phase 2" label so it is never mistaken for a bug.

## Tech Stack

Next.js 15 + React 19 + TypeScript + Tailwind. three.js (`three`, with `STLLoader` + `OrbitControls` from `three/examples/jsm`). Syntax highlighting: `react-syntax-highlighter` (Phase 1, read-only). Code editor (Phase 2): `@uiw/react-codemirror` with the Python language pack. E2E: Playwright (`tests/e2e/`).
