# Data Model

---

## Storage Technology

- **SQLite** via SQLAlchemy 2.0 (the harness default; single-user local app). DB URL `sqlite:///./data/agent.db` (env `AGENT_DATABASE_URL`). Schema is created/managed with **Alembic** — the Phase 1 gate runs `uv run alembic upgrade head`.
- **Local filesystem** holds the large artifacts (code, STL, STEP, preview PNG). The DB stores relative paths, not blobs.

The existing `runs` table is retained (one row per pipeline invocation — see the skeleton). Two new tables are added: `parts` and `versions`.

## Entities

### Entity: RunRow (`runs`) — retained from skeleton
One row per pipeline invocation (generate / modify / edit). Carries the transient run status and error, plus the token/cost and repair log of that invocation.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| id | Text (uuid) | yes | Primary key = `run_id` |
| status | Text | yes | `pending` \| `completed` \| `failed` |
| input_text | Text | no | The prompt (generate/modify) or `<edited code>` marker (edit) |
| output_text | Text | no | JSON blob of the run result envelope (generated_code, urls, repair log, tokens, cost) |
| error_message | Text | no | Set on failure |
| created_at / updated_at | Timestamp | yes | Existing |

> `output_text` stores the full result JSON so a run can be re-fetched via `GET /runs/{run_id}` without recomputation. `part_id`/`version_number` are also mirrored into the versions table below.

### Entity: PartRow (`parts`)
A part = one modification chain, born from a `generate_part` run.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| id | Text (uuid) | yes | Primary key = `part_id` |
| title | Text | yes | First ~60 chars of the originating prompt |
| latest_version | Integer | yes | Highest version number in the chain (denormalized for the gallery) |
| created_at | Timestamp | yes | When the part was first generated |
| updated_at | Timestamp | yes | Last version added |

### Entity: VersionRow (`versions`)
One row per successfully-persisted version (generate = v1, each modify/edit = +1). A version links to its parent to form the chain.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| id | Text (uuid) | yes | Primary key |
| part_id | Text (FK → parts.id) | yes | Owning part |
| version_number | Integer | yes | 1, 2, 3 … within the part |
| parent_version_id | Text (FK → versions.id) | no | Null for v1; set for modify/edit — the modification chain |
| source | Text | yes | `generate` \| `modify` \| `edit` |
| prompt | Text | no | The NL prompt for generate/modify; null for edit |
| model_id | Text | no | `gemini-3.5-flash` \| `gemini-3.1-flash-lite`; null for edit |
| code_path | Text | yes | Relative path to the CadQuery `.py` |
| stl_path | Text | yes | Relative path to the STL |
| step_path | Text | yes | Relative path to the STEP |
| thumbnail_path | Text | no | Relative path to preview PNG (Phase 2; null until captured) |
| repair_count | Integer | yes | Number of repair attempts used (0–3) |
| token_usage | Text (JSON) | no | `{prompt_tokens, completion_tokens, total_tokens}`; null for edit |
| cost_usd | Real | no | Estimated cost; null for edit |
| run_id | Text (FK → runs.id) | yes | The invocation that produced this version |
| created_at | Timestamp | yes | When produced |

> The **full schema above (including `parent_version_id`, `source`, `thumbnail_path`) ships in the Phase 1 Alembic migration.** Phase 1 only writes v1 rows with `source=generate`; Phase 2 populates `parent_version_id`, `source=modify/edit` and `thumbnail_path`. No second migration is required unless a later phase adds a column.

### Relationships

```
parts (1) ──< versions (N)          part_id FK
versions (1) ──< versions (N)       parent_version_id FK (self, modification chain)
runs  (1) ──< versions (0..1)       run_id FK
```

## Filesystem Layout (artifacts)

Root `artifacts/` at the repo root, served read-only at `/artifacts` (StaticFiles mount). Code is written under `generated_code/` (repo root) as the user explicitly requested a browsable `/generated_code` folder; STL/STEP/previews live under `artifacts/`.

```
generated_code/
  part_<part_id>/
    v1.py          v2.py      …        # versioned CadQuery source (also mirrored to artifacts for /artifacts URL)
artifacts/
  code/part_<part_id>/v<n>.py          # served copy of the code (code_url)
  exports/part_<part_id>/part_v<n>.stl # versioned STL (stl_url)
  exports/part_<part_id>/part_v<n>.step
  previews/part_<part_id>/v<n>.png     # client-captured thumbnail (Phase 2)
```

Versioning scheme: files are named `v<n>` / `part_v<n>` where `<n>` = `versions.version_number`. `<part_id>` is the uuid. Both `generated_code/` and `artifacts/code/` hold the source — `generated_code/` is the human-browsable folder the user asked for; `artifacts/code/` is the URL-served copy.

## Data Lifecycle

- **Create:** a part + v1 on each `generate_part`; a new version on each successful `modify`/`edit`. Files written before the DB row is committed; the row is the source of truth for "this version exists".
- **Update:** `parts.latest_version` / `updated_at` bumped when a version is added; `versions.thumbnail_path` set when the client uploads a thumbnail.
- **Delete:** none in scope (no delete/prune UI). Manual folder cleanup only. Out of scope for all phases.

## Sensitive Data

- No PII. The only secret is `AGENT_GEMINI_API_KEY` (in `.env`, never persisted, never returned to the client). Generated code is user content but non-sensitive.
