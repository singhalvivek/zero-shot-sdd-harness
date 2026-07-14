# API

---

## API Style

REST (FastAPI). All JSON responses use the skeleton envelope `{ "data": ..., "error": null }`; errors raise `HTTPException` with `detail = {code, message}` (see `src/api/_common.py`). Dev origin: single-origin — the built frontend is served at `http://localhost:8001/app/`, the API at the same origin, so no CORS. Static artifacts are served at `/artifacts/...`.

Phase 1 ships `POST /runs`, `GET /runs/{run_id}`, `GET /health`, and the `/artifacts` mount. Phase 2 adds the `/parts` endpoints.

---

## `POST /runs`  — generate_part *(Phase 1)*

**Purpose:** Generate a part from a prompt: LLM → safe exec → self-repair (≤3) → export → persist v1.

**Request:**
```json
{
  "prompt": "a 60x40x10mm bracket with two 5mm mounting holes",
  "model_id": "gemini-2.5-flash",
  "mode": "generate"
}
```
`mode` defaults to `generate`. `model_id` ∈ {`gemini-2.5-flash`, `gemini-2.5-pro`}.

**Response (`data`):**
```json
{
  "run_id": "uuid",
  "part_id": "uuid",
  "version_number": 1,
  "status": "completed",
  "generated_code": "import cadquery as cq\n...\nresult = ...",
  "repair_attempts": [
    { "attempt": 1, "error": "NameError: name 'Workplane' ...", "change_summary": "qualified cq.Workplane" }
  ],
  "safety_violation": null,
  "token_usage": { "prompt_tokens": 812, "completion_tokens": 240, "total_tokens": 1052 },
  "cost_usd": 0.0013,
  "stl_url": "/artifacts/exports/part_<id>/part_v1.stl",
  "step_url": "/artifacts/exports/part_<id>/part_v1.step",
  "code_url": "/artifacts/code/part_<id>/v1.py"
}
```
On a failed run: `status="failed"`, `error` populated in the top-level envelope's sibling field (or `data.status="failed"` with `data.safety_violation`/last error), `stl_url` null.

**Error cases:**
| Status | Condition |
|--------|-----------|
| 400 | missing/empty prompt, or `model_id` not in the allowed set |
| 200 + `status:"failed"` | safety violation, or execution still failing after 3 repairs, or export error (a *user-visible pipeline* failure, not an HTTP error) |
| 502 | Gemini API unreachable / auth error |
| 500 | unexpected internal error |

## `GET /runs/{run_id}`  *(Phase 1)*
Returns the persisted result envelope (`runs.output_text`) for a prior run — same `data` shape as above.

---

## `POST /parts/{part_id}/modify`  — modify_part *(Phase 2)*

**Request:** `{ "prompt": "make the holes 6mm", "model_id": "gemini-2.5-pro" }`
Server loads the latest (or specified) version's code as `previous_code`, runs the pipeline in `modify` mode, persists a new version linked to its parent. **Response:** same `data` shape as `POST /runs` with the incremented `version_number` and the parent linkage.

Optional `{ "from_version": <n> }` to branch from a specific version (defaults to latest).

## `POST /parts/{part_id}/rerun`  — edit_and_rerun *(Phase 2)*

**Request:** `{ "code": "<edited CadQuery>", "from_version": 2 }`
Runs the pipeline in `edit` mode (skips the LLM; safety-check + exec + export only; **no repair loop**). **Response:** `data` shape without `token_usage`/`cost_usd`; on exec error returns `status:"failed"` with the raw `exec_error` traceback for the editor.

## `GET /parts`  *(Phase 2)*
List parts, newest first: `data = [{ part_id, title, latest_version, thumbnail_url, created_at }]`.

## `GET /parts/{part_id}`  *(Phase 2)*
Part detail + full version chain: `data = { part_id, title, versions: [{ version_number, parent_version_id, source, prompt, model_id, stl_url, step_url, code_url, thumbnail_url, repair_count, created_at }] }`.

## `PUT /parts/{part_id}/versions/{version_number}/thumbnail`  *(Phase 2)*
**Request:** `{ "image_data_url": "data:image/png;base64,..." }` (captured from the viewer canvas). Stores the PNG, sets `versions.thumbnail_path`. **Response:** `data = { thumbnail_url }`. On decode/store error: log + `200` with `thumbnail_url: null` (non-critical).

## `GET /health`  *(existing)*
`data = { "status": "ok" }`.

---

## Static Artifacts

`GET /artifacts/**` — read-only StaticFiles mount over the `artifacts/` directory (STL, STEP, code copy, preview PNG). The 3D viewer fetches `stl_url` from here; download buttons point at `stl_url`/`step_url`/`code_url` with a `download` attribute.

## Authentication

None — single-user local app bound to localhost. No auth in any phase (documented out of scope).
