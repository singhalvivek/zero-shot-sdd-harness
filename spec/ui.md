# UI

## UI Type

Single-page web app: an upload step followed by a chat interface, both on one page (`frontend/src/app/page.tsx`).

## Views / Screens

### Screen: Upload + Chat (single page, two states)

**Purpose:** Let the user upload their one CSV, then ask it questions in a chat thread — the entire product surface lives on this one screen.

**Key elements (state 1 — no session yet, REAL):**
- File picker / drag-and-drop area for a single CSV file
- "Upload" button, disabled until a file is chosen
- Loading spinner while the upload is parsing
- Inline error message area (e.g. "File too large", "Could not parse this CSV")

**Key elements (state 2 — session active, REAL):**
- A small header strip showing the uploaded filename, row count, and column count (confirmation the real file was parsed)
- A scrollable chat message list: user questions right-aligned, assistant answers left-aligned, plain text only (no tables/charts/code blocks)
- A text input + "Ask" button (or Enter-to-send) for the next question
- A spinner shown in place of the next assistant bubble while a question is being answered (no step counter, no visible intermediate reasoning — per the product brief)
- An inline error banner (distinct styling from a normal answer bubble) for fatal errors (e.g. "Something went wrong answering that — try again"), separate from a normal "I don't have enough information" answer bubble, which is NOT an error state

**Key elements (labelled, NON-FUNCTIONAL stubs, clearly marked "coming soon" — never mistaken for a bug):**
- A disabled "Export answer" button next to each assistant message, with a tooltip "Coming soon"
- A disabled "Show chart" toggle next to the chat input, with a tooltip "Coming soon"

**Actions available:**
- Upload a CSV (state 1 → state 2)
- Ask a question (repeatable, within state 2)
- (Stub, inert) Export an answer
- (Stub, inert) Toggle a chart view

## Error States

- **Upload validation error** (wrong file type, too large, unparseable): inline red text under the upload control; the user can immediately pick a different file and retry — no page reload needed.
- **Chat fatal error** (session lost, LLM API failure): a distinct red-bordered banner bubble in the chat thread reading a plain "Something went wrong — please try asking again," rather than a bare stack trace or HTTP status.
- **Unanswerable question** (NOT an error — a normal, successfully-returned answer): rendered as a normal assistant bubble, plain text, saying the agent doesn't have enough information/context to answer — visually identical styling to any other answer, since it's a valid conversational outcome, not a failure.
- **Network error** (server unreachable): inline banner "Network error — is the server running?", matching the existing skeleton's pattern in `page.tsx`.

## Tech Stack

Next.js 15 + React 19 (existing skeleton, static export served by FastAPI at `/app/`), Tailwind CSS v4 for styling (existing `globals.css`/`postcss.config.mjs`, extended not replaced). Playwright (`@playwright/test`, already present in `frontend/node_modules`) provides the `tests/e2e/` smoke suite covering the primary journey (upload → ask → real answer).
