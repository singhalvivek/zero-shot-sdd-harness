# Capability: Token Usage & Audit Log (Phase 2)
## What It Does
Displays real per-query Gemini token usage and exposes a viewer of all persisted query/answer rows with timestamps.
## Inputs
| Input | Type | Source | Required |
| token counts | ints | answer/finalize nodes | yes |
| audit rows | AuditLog[] | `audit_log` table | yes |
## Outputs
| Output | Type | Destination |
| usage badge | ints | SSE `usage` + UI |
| audit list | JSON | `GET /audit` + Audit tab |
## External Calls
| System | Operation | On Failure |
| SQLite | Read audit_log | 500 (logged) |
## Business Rules
- Token counts come from the Gemini response usage metadata, accumulated across all node calls in the run.
- Audit log is append-only, newest first in the viewer.
## Success Criteria
- [ ] After a query, the UI shows non-zero prompt and completion token counts.
- [ ] `GET /audit` lists the just-asked query with its answer, tokens, and timestamp.
