# Agent

---

## Agent Architecture Pattern

**Chosen:** Graph (LangGraph) with a bounded refine loop and a runner-level human-in-the-loop clarify gate. A single graph runs `triage → plan → write_code → execute → refine → answer`; the refine loop (execute ↔ refine) handles the iterative "try → see result → fix" behaviour, which a linear loop cannot express cleanly. The graph is compiled **without a checkpointer** — conversation memory is provided by rehydrating prior message rows in the runner, and the clarify pause is a runner-level gate (triage→END), not a LangGraph interrupt (see Concurrency Model).

---

## LLM Provider & Model

| Agent / Node | Provider | Model ID | Rationale |
|-------------|----------|----------|-----------|
| triage (P2) | Gemini | `AGENT_LLM_MODEL` (default `gemini-3.1-pro`) | Cheap ambiguity check |
| plan | Gemini | same | Strategy reasoning |
| write_code / refine | Gemini | same | Code generation quality |
| answer | Gemini | same | Streamed natural-language phrasing |

**Fallback behaviour:** Gemini calls retry with exponential backoff (3 attempts). If still failing, the node sets `state["error"]` and routes to `handle_error`, which streams a user-facing error message. Tests call the real Gemini API via `.env` — no offline stub.

**Prompt strategy:** System/user split. `write_code`/`refine` use JSON-mode-style structured output (a fenced ```python block extracted by the node). Each prompt is given ONLY column names, dtypes, row count, and prior aggregate results — never raw rows or cell values (see `data.md` → Sensitive Data).

---

## Tools & Tool Calling

The agent does not use LLM tool-calling; it uses a deterministic graph. The one "tool" is the local sandbox, invoked by the `execute` node (not chosen by the LLM).

| Tool name | Description | Inputs | Output | Side-effects |
|-----------|-------------|--------|--------|--------------|
| `run_pandas` (`src/analysis/sandbox.py`) | Execute generated pandas in an isolated subprocess with named dataframes loaded | code str, dataset file paths | `{ok, result_repr, stdout, error}` | None (read-only on files) |

**Tool selection strategy:** Rule-based — `execute` always calls `run_pandas`. No LLM tool choice.

**Tool failure handling:** Captured error string is returned to the graph; `execute`'s conditional edge routes to `refine` (up to `MAX_REFINES`, default 3). After the cap, route to `answer` with a best-effort/error explanation.

---

## Agent State

```python
class AgentState(TypedDict, total=False):
    # Identity
    run_id: str                          # audit_log row id, set at init
    session_id: str                      # conversation/session id

    # Input
    question: str                        # the user's natural-language question
    dataset_paths: dict[str, str]        # {df_name: local_file_path}
    schemas: dict[str, dict]             # per-df: columns, dtypes, row_count (NO cell values)
    messages: list                       # prior [{role, content}] turns (conversation memory)

    # Pipeline data (populated by nodes)
    needs_clarification: bool            # triage (P2)
    clarifying_question: str | None      # triage (P2)
    plan: str                            # plan node
    code: str                            # write_code / refine
    exec_result: dict                    # sandbox output {ok, result_repr, stdout, error}
    refine_count: int                    # execute→refine loop counter

    # Output
    answer_text: str                     # answer node (streamed)
    suggestions: list[str]               # answer node, 2-3 follow-ups (P2)
    prompt_tokens: int                   # accumulated
    completion_tokens: int               # accumulated

    # Control
    error: str | None
    status: str                          # "completed" | "failed" | "needs_clarification"
```

---

## Nodes / Steps

### `node_triage` (entry node)
**Reads:** `question`, `schemas`, `messages`. **Writes:** `needs_clarification`, `clarifying_question`.
**LLM call:** yes — classifies whether the question is answerable as-is. **Behaviour:** if ambiguous, sets `needs_clarification=True` and a clarifying question; the triage conditional edge then routes to `END` (no planning). This is a **runner-level clarify gate**, not a LangGraph interrupt: the runner (`src/graph/runner.py` `_run_until_execute`) runs triage first and returns early when `needs_clarification` is set, so no analysis runs. The streaming runner emits an SSE `clarify` event followed by `done{status:"needs_clarification"}`; the user answers by sending a **new ask in the same session** (prior turns are rehydrated for context) — there is no in-graph pause/resume.

### `node_plan`
**Reads:** `question`, `schemas`, `messages`. **Writes:** `plan`.
**LLM call:** yes. **Behaviour:** produces a short ordered analysis strategy referencing dataframe/column names. Schema-only context.

### `node_write_code`
**Reads:** `plan`, `schemas`, `question`. **Writes:** `code`.
**LLM call:** yes (code gen). **Behaviour:** emits a pandas snippet that computes the answer and prints/assigns a `result` variable. Never reads raw rows into the prompt.

### `node_execute`
**Reads:** `code`, `dataset_paths`. **Writes:** `exec_result`.
**LLM call:** no. **External:** subprocess sandbox (`run_pandas`). On failure: captured error → conditional edge to `refine`.

### `node_refine`
**Reads:** `code`, `exec_result.error`, `plan`. **Writes:** `code`, increments `refine_count`.
**LLM call:** yes. **Behaviour:** rewrites the code given the captured error/traceback, then loops back to `execute`.

### `node_answer`
**Reads:** `exec_result.result_repr`, `question`, `messages`. **Writes:** `answer_text`, `suggestions` (P2), token counts, appends to `messages`.
**LLM call:** yes, **streamed**. **Behaviour:** turns the aggregate result into plain language with key numbers called out; emits 2–3 follow-up suggestions (P2).

### `node_finalize`
Persists the `audit_log` row (question, answer, token counts, timestamp), sets `status="completed"`.

### `node_handle_error`
Sets `status="failed"`, writes `error` to `audit_log`, streams a graceful error message.

---

## Graph / Flow Topology

```
START
  │
  ▼
node_triage ──(needs_clarification)──► END (returns clarifying question)   [P2]
  │ (clear)
  ▼
node_plan ──(error)──► node_handle_error ──► END
  │
  ▼
node_write_code ──► node_execute
                       │
        (ok)           │  (error & refine_count < MAX_REFINES)
        │              ▼
        │          node_refine ──► node_execute   (loop)
        │              │ (refine_count >= MAX_REFINES)
        ▼              ▼
      node_answer ◄────┘
        │
        ▼
   node_finalize ──► END
```

**Conditional edges:**

| Source node | Condition | Target |
|-------------|-----------|--------|
| node_triage | `needs_clarification` | END (return clarifying question) |
| node_triage | else | node_plan |
| any node | `state["error"]` set | node_handle_error |
| node_execute | `exec_result.ok` | node_answer |
| node_execute | error & `refine_count < MAX_REFINES` | node_refine |
| node_execute | error & `refine_count >= MAX_REFINES` | node_answer (best-effort/error) |
| node_refine | always | node_execute |

---

## Memory & Context

| Scope | Mechanism | What is stored |
|-------|-----------|----------------|
| Within a run | LangGraph state | plan, code, exec results |
| Across runs | SQLite `message` + `audit_log` | conversation turns, query/answer history |
| Conversation | `messages` list rehydrated from `message` table per session | prior user/assistant turns for follow-ups |

**Context window management:** Only column names + dtypes + aggregate results enter prompts. Conversation history is passed as prior turns; if long, the oldest turns are truncated (sliding window of recent turns). Never raw rows or cell values.

---

## Human-in-the-Loop Checkpoints

| Checkpoint | What is shown | Expected action | Timeout / default |
|------------|---------------|-----------------|-------------------|
| Clarify | The agent's clarifying question | User answers by sending a new ask in the same session | None — user re-asks |

**Mechanism (runner gate, not a checkpointer interrupt):** the clarify pause is implemented at the runner level, not as a LangGraph interrupt/resume. `triage` is the graph entry node; when it sets `needs_clarification`, its conditional edge routes to `END` and `src/graph/runner.py` `_run_until_execute` returns early before any planning/execution. The streaming path emits an SSE `clarify` event then `done{status:"needs_clarification"}`. There is no suspended graph state to resume: the user's follow-up is a fresh ask on the same session, and the prior turns rehydrated from the `message` table supply the context that answers the clarifying question.

---

## Error Handling & Recovery

**Node-level:** each node wraps its body in try/except; fatal errors set `state["error"]` and route to `handle_error`.

**Graph-level (handle_error node):** reads `error`, `run_id`; updates `audit_log` (status failed, error message); streams a graceful message; terminates.

**Resume / retry strategy:** the execute→refine loop is the in-graph retry (bounded by `MAX_REFINES`). A failed run is not auto-resumed; the user re-asks.

**Partial failure:** if the sandbox keeps failing after `MAX_REFINES`, `answer` produces a best-effort explanation rather than crashing.

---

## Observability

| Signal | What | Where |
|--------|------|-------|
| Trace | one trace per ask, one span per node | structured stdout log (`src/observability/events.py`) |
| LLM calls | prompt/completion tokens, latency, model, node | structured log + `audit_log` token columns |
| Sandbox calls | code hash, ok/error, latency | structured log (code body NOT logged with raw data) |
| Run outcome | status, duration, error | `audit_log` + structured log |

---

## Concurrency Model

- **Run isolation:** single user; one ask per session processed at a time. Concurrent asks across sessions are run_id-scoped.
- **Parallel nodes within a run:** none (sequential pipeline).
- **Checkpointing:** **none.** The StateGraph is compiled with **no checkpointer** (`graph.compile()`). Conversation continuity is provided by rehydrating prior `Message` rows from SQLite in the runner (`src/graph/runner.py` `_load_messages` → `state["messages"]`), not by a LangGraph `SqliteSaver`. Each ask starts a fresh graph run seeded with the rehydrated turns.

> **Design note:** No checkpointer is intentional for this app. It is single-user and streaming-first, so there is no concurrent-run state to persist and no in-graph interrupt to resume. Conversation memory via DB message rehydration is simpler, keeps the streaming path clean, and makes the clarify flow a plain runner-level gate (triage→END on ambiguity, follow-up ask supplies the answer) rather than a checkpointer suspend/resume.

---

## Graph Assembly (`src/graph/agent.py`)

```python
graph = StateGraph(AgentState)

graph.add_node("triage", node_triage)
graph.add_node("plan", node_plan)
graph.add_node("write_code", node_write_code)
graph.add_node("execute", node_execute)
graph.add_node("refine", node_refine)
graph.add_node("answer", node_answer)
graph.add_node("finalize", node_finalize)
graph.add_node("handle_error", node_handle_error)

graph.set_entry_point("triage")

# Ambiguous questions route to END — the runner-level clarify gate handles them
# (no checkpointer interrupt); a clear question proceeds to plan.
graph.add_conditional_edges("triage", route_after_triage,
    {"plan": "plan", "clarify": END})
graph.add_conditional_edges("plan", route_after_plan,
    {"write_code": "write_code", "handle_error": "handle_error"})
graph.add_edge("write_code", "execute")
graph.add_conditional_edges("execute", route_after_execute,
    {"answer": "answer", "refine": "refine", "handle_error": "handle_error"})
graph.add_edge("refine", "execute")
graph.add_edge("answer", "finalize")
graph.add_edge("finalize", END)
graph.add_edge("handle_error", END)

# NO checkpointer — intentional (see Concurrency Model → Design note). Conversation
# continuity is provided by rehydrating prior Message rows in the runner, and the
# clarify pause is a runner-level gate (triage→END), not a checkpointer interrupt.
compiled_graph = graph.compile()
```

**Runner integration:** `src/graph/runner.py` seeds `state["messages"]` from the `message` table (DB rehydration) before each run, runs triage first, and returns early when `needs_clarification` is set — emitting an SSE `clarify` event then `done{status:"needs_clarification"}` instead of resuming an interrupted graph.
