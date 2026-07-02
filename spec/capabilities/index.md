# Capabilities Index

## What Is a Capability?

A capability is a single, discrete action or behavior the agent performs.

## Capabilities in This Project

| Capability | File |
|-----------|------|
| Upload CSV | [upload-csv.md](upload-csv.md) |
| Ask a Question About the CSV | [ask-question.md](ask-question.md) |
| Conversation Memory Within a Session | [conversation-memory.md](conversation-memory.md) |

All three ship together in Phase 1 — see [`spec/roadmap.md`](../roadmap.md) `## Phases of Development`.

## How to Add a New Capability

Run `/zero-shot-build [description]` on the existing spec. The spec-writer sub-agent will:
1. Create a new file in this directory (`<name>.md`, no number prefix)
2. Update this index
3. Flag any dependencies on existing capabilities
4. Self-review that it fits the architecture and data model before returning

## Capability File Template

Each capability file should answer:
- **What it does** (one sentence)
- **Inputs** (what data it receives)
- **Outputs** (what it produces)
- **External calls** (APIs, LLMs, databases it touches)
- **Business rules**
- **Success criteria** (how we test it)
