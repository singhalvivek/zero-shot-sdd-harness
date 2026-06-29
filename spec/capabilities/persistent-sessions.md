# Capability: Persistent Sessions (Phase 3)
## What It Does
Lets the user resume a prior session across restarts, with its datasets and conversation history still loaded.
## Inputs
| Input | Type | Source | Required |
| session list request | — | UI switcher | yes |
| session_id | str | User selection | yes |
## Outputs
| Output | Type | Destination |
| session list | JSON | `GET /sessions` |
| resumed session | JSON | `GET /sessions/{id}` |
## External Calls
| System | Operation | On Failure |
| SQLite | Read sessions/messages/bindings | 500 |
## Business Rules
- Sessions, dataset bindings, and messages persist in SQLite across restarts.
- Switcher lists sessions newest-first by `updated_at`.
## Success Criteria
- [ ] After restarting the app, a prior session can be selected and its history + datasets are available for new questions.
