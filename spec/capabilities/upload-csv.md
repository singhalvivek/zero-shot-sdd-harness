# Capability: Upload CSV

## What It Does
Parses one user-uploaded CSV file into an in-memory session (DataFrame + schema) and returns a confirmation summary, with no proactive profiling or suggestions.

## Inputs
| Input | Type | Source | Required |
|-------|------|--------|----------|
| file | multipart file (CSV) | Browser upload form | yes |

## Outputs
| Output | Type | Destination |
|--------|------|-------------|
| session_id | string (UUID4) | Returned to browser; held in React state for all later chat calls |
| filename, row_count, columns | struct | Rendered in the upload confirmation header |

## External Calls
| System | Operation | On Failure |
|--------|-----------|------------|
| In-memory session store | create a new `Session` entry keyed by `session_id` | fatal for this request — 500, no session created |

## Business Rules
- Exactly one CSV per session; a second upload in the same tab starts a brand-new session (new `session_id`), it does not append to or replace the old one's data.
- Max upload size 10MB; larger files are rejected with a 400 and a plain "file too large" message before any parse is attempted.
- Only `.csv`/`text/csv`-ish content is accepted; non-CSV files (by extension and by parse failure) are rejected with a 400.
- The agent does NOT proactively compute or surface summary statistics, data-quality warnings, or suggested questions on upload — only filename, row count, and column names are shown, purely as upload confirmation.
- No file bytes are persisted to disk; the parsed DataFrame lives only in the in-memory session store.

## Success Criteria
- [ ] Uploading a valid CSV ≤10MB returns 200 with a `session_id`, correct `row_count`, and the exact column names from the file.
- [ ] Uploading a file >10MB returns 400 without attempting to parse it.
- [ ] Uploading a non-CSV or malformed CSV returns 400 with a plain, non-technical error message.
- [ ] The response never includes computed statistics, suggested questions, or any content beyond filename/row_count/columns/session_id.
