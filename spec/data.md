# Data Model

---

## Storage Technology

SQLite + SQLAlchemy 2.0, migrated with Alembic. SQLite is the production database for this single-user local app (tests use SQLite too). Uploaded files are stored on the local filesystem under `data/uploads/`; only metadata and a path are stored in the DB.

## Entities

### Entity: Dataset
An uploaded tabular file and its profiled schema.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| id | str (uuid) | yes | Primary key |
| df_name | str | yes | Name the agent references the frame by (e.g. `sales`) |
| filename | str | yes | Original filename |
| file_path | str | yes | Local path under `data/uploads/` |
| file_type | str | yes | `csv` (P1) or `xlsx` (P3) |
| row_count | int | yes | Rows profiled at upload |
| schema_json | JSON (text) | yes | Columns + dtypes only (NO data values) |
| created_at | timestamp | yes | Upload time |

### Entity: Session
A conversation session that binds one or more datasets and holds message history.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| id | str (uuid) | yes | Primary key |
| title | str | no | Optional label (Phase 3 switcher) |
| created_at | timestamp | yes | |
| updated_at | timestamp | yes | Last activity (for resume ordering) |

### Entity: SessionDataset
Join: which datasets are loaded into a session.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| session_id | str (fk) | yes | → Session.id |
| dataset_id | str (fk) | yes | → Dataset.id |

### Entity: Message
One conversation turn (rehydrated into `state.messages`).

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| id | str (uuid) | yes | Primary key |
| session_id | str (fk) | yes | → Session.id |
| role | str | yes | `user` or `assistant` |
| content | text | yes | Turn text |
| created_at | timestamp | yes | |

### Entity: AuditLog
Persisted record of every query and answer.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| id | str (uuid) | yes | Primary key (also `run_id`) |
| session_id | str (fk) | yes | → Session.id |
| question | text | yes | The user's question |
| answer | text | no | The streamed answer (null if failed) |
| prompt_tokens | int | no | Gemini prompt tokens |
| completion_tokens | int | no | Gemini completion tokens |
| status | str | yes | `completed` / `failed` / `needs_clarification` |
| error_message | text | no | On failure |
| created_at | timestamp | yes | Query time |

### Relationships
- Session 1—N Message, 1—N AuditLog.
- Session N—N Dataset via SessionDataset.

> The skeleton's `runs` table is superseded by `audit_log`; the migration replaces the `transform_text` capability slot.

## Data Lifecycle
- Dataset created on upload; file persists under `data/uploads/` until manually deleted. Read-only.
- Messages and audit rows are append-only, retained for the audit log; never auto-purged.
- Sessions persist across restarts (Phase 3 resume).

## Sensitive Data
- Uploaded files contain the user's raw data — they NEVER leave the machine and are never sent to the LLM. Only column names + dtypes (`schema_json`) and computed **aggregate** results may appear in any prompt.

> **Assumed:** the LLM is given column names, dtypes, and row count — but NOT `df.head()` values — to hold the rows-never-leave guarantee strictly. (The brief mentioned `df.head` as candidate context; we exclude actual cell values to keep the privacy bar absolute. If the user prefers a 5-row sample for better code generation, it can be enabled as a documented exception.)
