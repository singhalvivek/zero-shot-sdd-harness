# API

---

## API Style

REST + Server-Sent Events (SSE) for streamed answers. FastAPI at `:8001`; the static Next.js export is served at `:8001/app/`.

## Endpoints / Commands

### `POST /datasets`  (Phase 1; multi-file/Excel in Phase 3)

**Purpose:** Upload a tabular file, profile its schema, store it locally, return its dataset record.

**Request:** `multipart/form-data` with `file` (CSV; xlsx in P3) and optional `session_id`, `df_name`.

**Response:**
```json
{ "ok": true, "data": { "dataset_id": "uuid", "df_name": "sales", "row_count": 1200,
  "columns": [{"name": "dept", "dtype": "object"}], "session_id": "uuid" } }
```

**Error cases:**
| Status | Condition |
|--------|-----------|
| 400 | Unreadable/unsupported file, or empty table |
| 500 | Storage/profiling failure |

### `POST /sessions/{session_id}/ask`  (Phase 1)

**Purpose:** Ask a natural-language question; stream the plain-language answer.

**Request:**
```json
{ "question": "what is the average salary by department?" }
```

**Response:** `text/event-stream` SSE. Event types:
- `token` — `{ "text": "partial answer..." }` (streamed answer chunks)
- `clarify` (P2) — `{ "question": "Which metric do you mean?" }`
- `suggestions` (P2) — `{ "items": ["...", "..."] }`
- `usage` — `{ "prompt_tokens": 812, "completion_tokens": 96 }`
- `done` — `{ "run_id": "uuid", "status": "completed" }`
- `error` — `{ "message": "..." }`

**Error cases:**
| Status | Condition |
|--------|-----------|
| 404 | Unknown session |
| 400 | No dataset bound to session / empty question |
| 500 | Agent failure after retries (also emitted as SSE `error`) |

### `GET /sessions/{session_id}`  (Phase 1)

**Purpose:** Fetch a session with its bound datasets and message history.

**Response:**
```json
{ "ok": true, "data": { "session_id": "uuid", "datasets": [...], "messages": [{"role": "user", "content": "..."}] } }
```

### `GET /audit`  (Phase 2)

**Purpose:** List persisted query/answer/token rows (audit-log viewer).

**Response:** `{ "ok": true, "data": [{ "id": "uuid", "question": "...", "answer": "...", "prompt_tokens": 812, "completion_tokens": 96, "created_at": "..." }] }`

### `GET /sessions`  (Phase 3)

**Purpose:** List sessions for the resume switcher, newest first.

## Authentication

None — single local user on localhost. No auth layer.
