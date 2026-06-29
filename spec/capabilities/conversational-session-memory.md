# Capability: Conversational Session Memory
## What It Does
Keeps files and conversation history loaded across a session so follow-up questions ("now break that down by region") resolve against prior turns and the same dataframes.
## Inputs
| Input | Type | Source | Required |
| session_id | str | Client | yes |
| new question | str | User | yes |
| prior turns | Message[] | `message` table | no |
## Outputs
| Output | Type | Destination |
| Persisted turns | Message rows | `message` table |
| Rehydrated `messages` | list | Agent state |
## External Calls
| System | Operation | On Failure |
| SQLite | Read/write message turns | 500 (logged) |
## Business Rules
- Each ask appends a `user` and an `assistant` message to the session.
- The agent receives prior turns as context (sliding window if long).
- Datasets bound to the session stay available for every turn without re-upload.
## Success Criteria
- [ ] After asking "avg salary by dept", a follow-up "break that down by gender" answers without re-stating the subject.
- [ ] Reloading `GET /sessions/{id}` returns the full message history in order.
