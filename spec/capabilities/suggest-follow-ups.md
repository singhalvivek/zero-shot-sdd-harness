# Capability: Suggest Follow-ups (Phase 2)
## What It Does
After each answer, suggests 2–3 relevant follow-up questions the user can click to ask next.
## Inputs
| Input | Type | Source | Required |
| answer + result | str/JSON | answer node | yes |
| schemas | JSON | state | yes |
## Outputs
| Output | Type | Destination |
| suggestions | str[] (2–3) | SSE `suggestions` event |
## External Calls
| System | Operation | On Failure |
| Gemini (answer node) | Generate follow-ups | Omit suggestions (non-fatal) |
## Business Rules
- 2–3 suggestions, each a valid standalone question against the loaded data.
- Clicking a chip submits it as the next ask.
## Success Criteria
- [ ] Each completed answer returns 2–3 follow-up suggestions.
- [ ] Clicking a suggestion asks that question.
