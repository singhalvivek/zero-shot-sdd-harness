# API

## API Style

REST (JSON over HTTP), served by the existing FastAPI app. Replaces the skeleton's generic `/runs` demo surface with two capability-specific endpoints. `/health` (existing) is unchanged.

## Endpoints / Commands

### `POST /uploads`

**Purpose:** Upload one CSV file and start a new session.

**Request:** `multipart/form-data` with a single field `file` (the CSV). Max size 10MB (business rule — see [`upload-csv`](capabilities/upload-csv.md)).

**Response:**
```json
{
  "data": {
    "session_id": "b3f1...-uuid",
    "filename": "orders.csv",
    "row_count": 1204,
    "columns": ["order_id", "customer", "amount", "region", "order_date"]
  }
}
```

**Error cases:**
| Status | Condition |
|--------|-----------|
| 400 | No file provided, file is not CSV, file exceeds 10MB, or the CSV fails to parse (e.g. malformed/empty) |
| 500 | Unexpected server error while parsing/storing the session |

---

### `POST /sessions/{session_id}/messages`

**Purpose:** Ask a plain-language question about the session's uploaded CSV and get back a plain-language answer, in the context of the session's prior chat turns.

**Request:**
```json
{
  "question": "What is the total revenue?"
}
```

**Response:**
```json
{
  "data": {
    "answer": "The total revenue across all 1,204 orders is $482,910.35.",
    "status": "completed"
  }
}
```

**Error cases:**
| Status | Condition |
|--------|-----------|
| 400 | `question` missing or empty |
| 404 | `session_id` not found (session expired/server restarted, or never existed) |
| 422 | A fatal graph error occurred (e.g. LLM API unreachable) — `status: "failed"` with a plain `error` message in the response body; note this is **not** the "unanswerable question" case, which returns `status: "completed"` with an honest plain-language answer (200) |
| 500 | Unexpected server error |

Note: an *unanswerable* question (missing column, insufficient data) is a successful response (`status: "completed"`, 200) whose `answer` text says the agent doesn't have enough information — this is a designed capability outcome, not an API error. See [`ask-question`](capabilities/ask-question.md) business rules.

### `GET /sessions/{session_id}` (supporting endpoint)

**Purpose:** Re-fetch the session's schema summary and full message history — used by the frontend to restore the chat panel after a page reload within the same tab session (since state otherwise lives only in React memory).

**Response:**
```json
{
  "data": {
    "session_id": "b3f1...-uuid",
    "filename": "orders.csv",
    "row_count": 1204,
    "columns": ["order_id", "customer", "amount", "region", "order_date"],
    "messages": [
      {"role": "user", "content": "What is the total revenue?"},
      {"role": "assistant", "content": "The total revenue across all 1,204 orders is $482,910.35."}
    ]
  }
}
```

**Error cases:**
| Status | Condition |
|--------|-----------|
| 404 | `session_id` not found |

## Authentication

None — single-user local tool, no auth. Sessions are identified solely by the unguessable `session_id` (UUID4) returned at upload time; there is no login, no user accounts, and no access control beyond "you must know the session_id" (acceptable per the stated constraints — this is not a multi-tenant or internet-exposed service).
