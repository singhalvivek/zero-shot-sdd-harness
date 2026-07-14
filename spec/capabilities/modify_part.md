# Capability: Modify Part

## What It Does
Refines an existing part with a natural-language follow-up ("make the holes 6mm", "add a fillet on the top edge"), producing a new version in the same modification chain by editing the prior version's code rather than starting over.

## Inputs
| Input | Type | Source | Required |
|-------|------|--------|----------|
| part_id | string | selected part (viewer / history) | yes |
| prompt | string (the follow-up instruction) | user (follow-up box) | yes |
| model_id | enum `gemini-2.5-flash` \| `gemini-2.5-pro` | user (model selector) | yes |

The prior version's `generated_code` is loaded server-side and passed as `previous_code` — this is the iterative memory: the model receives the code it is modifying, not a blank slate.

## Outputs
| Output | Type | Destination |
|--------|------|-------------|
| new version_number (parent = prior version) | int | `versions` row with `parent_version_id` set (see [data.md](../data.md)) |
| generated_code, stl_url, step_url, code_url, repair_attempts, token_usage, cost_usd | same shape as `generate_part` | response body → viewer + panels |

## External Calls
Same as [generate_part](generate_part.md) — Gemini (with `previous_code` in context), sandboxed CadQuery execution, filesystem. Same repair loop and safety check.

## Business Rules
- The system instruction, when `previous_code` is present, instructs the model to treat the request as a **modification** — edit the supplied code, keep unrelated parameters intact, do not regenerate from scratch.
- The new version links to its parent via `parent_version_id`, forming the modification chain.
- All `generate_part` safety, timeout and repair rules apply unchanged.

## Success Criteria
- [ ] A follow-up on an existing part produces `version_number = parent + 1` with `parent_version_id` referencing the prior version.
- [ ] The new code visibly derives from the prior code (e.g. a "holes to 6mm" follow-up changes the hole-diameter constant while other constants persist) — asserted against the real Gemini key.
- [ ] The new version's STL differs from the parent's STL (different geometry / file hash) for a dimension-changing follow-up.
- [ ] The version chain is retrievable via the parts detail endpoint.
