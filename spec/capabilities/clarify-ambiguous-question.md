# Capability: Clarify Ambiguous Question (Phase 2)
## What It Does
Detects when a question is ambiguous and pauses to ask the user a clarifying question before planning/running any analysis.
## Inputs
| Input | Type | Source | Required |
| question | str | User | yes |
| schemas + history | JSON | state | yes |
## Outputs
| Output | Type | Destination |
| clarifying_question | str | SSE `clarify` event |
| status `needs_clarification` | str | `audit_log` |
## External Calls
| System | Operation | On Failure |
| Gemini (triage node) | Classify ambiguity | Retry then proceed as non-ambiguous |
## Business Rules
- On ambiguity, the graph interrupts before `plan`; no pandas runs.
- The user's answer is sent as a new ask that resumes with the clarification in context.
## Success Criteria
- [ ] An ambiguous question ("which is the best one?") yields a clarifying question, not an answer.
- [ ] A clear question proceeds straight to analysis with no clarification.
