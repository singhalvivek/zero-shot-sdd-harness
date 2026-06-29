# Capability: Multi-file Join & Compare (Phase 3)
## What It Does
Loads multiple named dataframes into the sandbox so the agent can answer questions that join or compare across files.
## Inputs
| Input | Type | Source | Required |
| multiple datasets | Dataset[] | session binding | yes |
| question | str | User | yes |
## Outputs
| Output | Type | Destination |
| Answer using >1 frame | SSE stream | Browser |
## External Calls
| System | Operation | On Failure |
| Local sandbox | Run pandas across named frames | refine loop |
## Business Rules
- Each dataset is exposed in the sandbox by its `df_name`.
- Planner/code-writer prompts list all bound frames + their schemas.
## Success Criteria
- [ ] A question comparing two files returns a correct joined/compared result matching a hand-computed pandas merge.
