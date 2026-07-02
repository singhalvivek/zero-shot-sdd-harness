# Data Model

## Storage Technology

Two distinct storage mechanisms, deliberately kept separate:

1. **In-memory session store** (`src/session/store.py`) — the source of truth for the uploaded CSV (as a pandas DataFrame) and the live chat history. Not backed by any database; lives only for the process lifetime and is lost on restart, matching the product requirement that nothing must persist beyond the live session.
2. **SQLite** (`AGENT_DATABASE_URL`, existing skeleton default) via SQLAlchemy 2.0 + Alembic — used only as a durable **observability log** of each analysis question/answer (for debugging and audit-of-behaviour), never as the mechanism that makes the chat/session actually work.

## Entities

### Entity: Session (in-memory only, not a DB table)

Represents one uploaded CSV and its ongoing chat conversation. Lives in a process-global dict keyed by `session_id`.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| session_id | string (UUID4) | yes | Identifies the session; minted on upload, held by the browser tab only |
| filename | string | yes | Original uploaded filename, for display |
| df | pandas.DataFrame | yes | The parsed CSV, held in memory |
| columns | list[string] | yes | Column names, derived from `df.columns` |
| dtypes | dict[string, string] | yes | Column name → pandas dtype string, derived from `df.dtypes` |
| row_count | int | yes | `len(df)`, derived |
| created_at | datetime | yes | When the session was created |
| messages | list[Message] | yes | Ordered chat turns for this session (see below); starts empty |

### Entity: Message (in-memory, part of a Session's `messages` list — not a standalone DB row)

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| role | enum("user", "assistant") | yes | Who produced this turn |
| content | string | yes | The question text (user) or the final plain-language answer (assistant) — never the intermediate code/critique |
| created_at | datetime | yes | Turn timestamp |

### Entity: AnalysisRunRow (SQLite table `analysis_runs`, new — separate from the skeleton's `runs` table)

An observability-only log of each chat question processed by the agent graph. Not read back by the chat flow; exists purely so a developer can inspect what happened after the fact.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| id | string (UUID4), PK | yes | Primary key |
| session_id | string | yes | Which session this question belonged to (no FK — the session may no longer exist in memory) |
| question | text | yes | The user's question |
| answer | text | no | The final plain-language answer, once completed |
| status | text | yes | `"completed"` \| `"failed"` |
| error_message | text | no | Set when `status = "failed"` |
| iterations | integer | no | How many write→execute→critique attempts the graph made before finishing |
| created_at | timestamp (tz-aware) | yes | Row creation time |
| updated_at | timestamp (tz-aware) | yes | Last update time |

### Relationships

`AnalysisRunRow.session_id` is a loose, non-enforced reference to an in-memory `Session.session_id` — there is intentionally no foreign key, since the in-memory session can vanish (process restart) while the log row persists. A `Session` has many `Message`s (its `messages` list, in-memory, unordered by any DB relation — just list order).

## Data Lifecycle

- **Session:** created on `POST /uploads`; updated on every chat turn (both the user's question and the assistant's answer are appended to `messages`); deleted only when the process restarts (no explicit delete endpoint in Phase 1 — out of scope, see roadmap).
- **AnalysisRunRow:** created (status implicitly "in-flight" until written) at `finalize`/`handle_error` time, i.e. one row per completed-or-failed chat question; never updated after creation in Phase 1 (no edit/delete); never automatically purged — acceptable for a personal/local prototype tool with small data volume.
- **Uploaded CSV file bytes:** never written to disk — parsed directly from the upload stream into a DataFrame held in memory; discarded when the session is discarded.

## Sensitive Data

- The uploaded CSV's contents (and therefore the DataFrame in memory, and any values echoed back in `AnalysisRunRow.answer`/`question`) may contain whatever data the user chooses to upload — this is treated as the user's own local data, consistent with the brief's "no data-residency lockdown, single-user personal tool" constraint. No PII-specific handling, masking, or encryption is implemented in Phase 1.
- API keys (`AGENT_ANTHROPIC_API_KEY`, `AGENT_GEMINI_API_KEY`) are read from `.env` only, confirmed by presence, never logged or echoed — per the existing skeleton convention and `harness/patterns/tech-stack.md`.
