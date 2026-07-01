# Capabilities Index

> One file per capability — each describes exactly one discrete thing the agent can do.

---

## Capabilities in This Project

| Capability | File | Phase |
|-----------|------|-------|
| Upload CSV | [upload_csv.md](upload_csv.md) | 1 |
| Ask Question (plan→pandas→refine, w/ conversation memory) | [ask_question.md](ask_question.md) | 1 |
| Stream Answer | [stream_answer.md](stream_answer.md) | 1 |
| Clarify Ambiguous Question | [clarify-ambiguous-question.md](clarify-ambiguous-question.md) | 2 |
| Suggest Follow-ups | [suggest-follow-ups.md](suggest-follow-ups.md) | 2 |
| Token Usage & Audit Log | [token-usage-and-audit-log.md](token-usage-and-audit-log.md) | 2 |
| Multi-file Join & Compare | [multi-file-join-and-compare.md](multi-file-join-and-compare.md) | 3 |
| Excel Support | [excel-support.md](excel-support.md) | 3 |
| Persistent Sessions | [persistent-sessions.md](persistent-sessions.md) | 3 |

## How to Add a New Capability

Run `/zero-shot-build [description]` on the existing spec. The spec-writer sub-agent will:
1. Create a new file in this directory (`<name>.md`, no number prefix)
2. Update this index
3. Flag any dependencies on existing capabilities
4. Self-review that it fits the architecture and data model before returning

## Capability File Template

Each capability file answers: What it does (one sentence), Inputs, Outputs, External calls, Business rules, Success criteria.
