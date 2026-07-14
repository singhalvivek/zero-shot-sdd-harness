# Capabilities Index

> One file per capability. Each describes exactly one discrete thing AI CAD Studio can do.

---

## What Is a Capability?

A single, discrete action the app performs end-to-end for the user.

## Capabilities in This Project

| Capability | File | First real in |
|-----------|------|---------------|
| Generate a 3D part from plain English (generate → safe-exec → self-repair → export → view) | [generate_part.md](generate_part.md) | Phase 1 |
| Modify an existing part with a natural-language follow-up (new version in the chain) | [modify_part.md](modify_part.md) | Phase 2 |
| Hand-edit the CadQuery code and re-run it | [edit_and_rerun.md](edit_and_rerun.md) | Phase 2 |
| Browse the history of past parts, versions and modification chains | [browse_history.md](browse_history.md) | Phase 2 |

Token/cost accounting and per-version file persistence are **outputs of** `generate_part` (not separate capabilities); they are visible from Phase 1. Preview thumbnails are produced during `browse_history` (Phase 2).

## How to Add a New Capability

Run `/zero-shot-build [description]` on the existing spec. The spec-writer creates a new `<name>.md`, updates this index, and self-reviews fit against the architecture, data model and agent graph.

## Capability File Template

- **What it does** (one sentence)
- **Inputs / Outputs / External calls**
- **Business rules**
- **Success criteria** (testable)
