# Agent

## Agent Architecture Pattern

| Pattern | Use when |
|---------|----------|
| **Single-agent loop** | One LLM drives a deterministic tool-call loop. No branches, no handoffs. |
| **Graph (LangGraph)** | Multi-step pipeline with conditional edges, checkpointing, or parallel nodes. |
| **Multi-agent** | Specialised sub-agents with distinct roles; orchestrator routes between them. |
| **Supervisor** | One supervisor LLM dispatches to worker agents based on task type. |
| **Human-in-the-loop** | Execution pauses at defined checkpoints for user review or approval. |

**Chosen:** Graph (LangGraph), composing two catalogue patterns from `harness/patterns/agentic-ai.md`: **#22 LLM-Generated Code Execution** (the LLM writes real pandas code that the system executes, rather than a fixed op-list or a guessed number) wrapped in a **#4 Reflection** loop (a critique step inspects the execution outcome and drives bounded retry before the answer is finalized). This is a step *up* from the base ReAct loop, justified because the product's entire value proposition is "never hallucinate a number" — a single write-then-answer pass cannot self-correct a wrong or failing pandas snippet.

---

## LLM Provider & Model

| Agent / Node | Provider | Model ID | Rationale |
|-------------|----------|----------|-----------|
| `write_code` | Anthropic | `claude-sonnet-4-6` | Writing correct pandas code from a plain-language question needs strong reasoning; called at most `max_iterations` times per question. |
| `critique` | Anthropic | `claude-haiku-4-5-20251001` | A small structured verdict (confident / retry / unanswerable) on every attempt — cheap/fast model keeps the retry loop responsive. |
| `compose_answer` | Anthropic | `claude-sonnet-4-6` | Final user-facing prose; quality matters more than latency here since it runs once per question. |

Model IDs are read from `Settings.llm_model` (existing) and a new `Settings.llm_model_fast` (default `claude-haiku-4-5-20251001`), both overridable via `AGENT_LLM_MODEL` / `AGENT_LLM_MODEL_FAST` env vars — never hardcoded in node code.

**Fallback behaviour:** any LLM call raising (timeout, 4xx/5xx, malformed response) is caught by the node and sets `state["error"]`, routing to `handle_error`. No automatic cross-provider fallback in Phase 1 (single provider, Anthropic) — the existing `LLMClient` auto-detects Anthropic vs. Gemini from whichever key is present, so this graph works unmodified if the user later sets `AGENT_GEMINI_API_KEY` instead.

**Prompt strategy:** system/user split via prompt files in `src/prompts/` (`write_code.md`, `critique.md`, `compose_answer.md`), matching the skeleton's `transform.md` convention. `write_code` and `critique` request structured output (`write_code` returns a fenced python block containing only the analysis code; `critique` returns a strict one-line JSON verdict `{"verdict": "confident"|"retry"|"unanswerable", "feedback": "..."}`, parsed defensively — a parse failure is treated as `"retry"` with feedback "could not parse critique, retrying"). `compose_answer` returns plain prose, no structure required.

---

## Tools & Tool Calling

| Tool name | Description | Inputs | Output | Side-effects |
|-----------|-------------|--------|--------|--------------|
| `run_pandas_code` | Executes LLM-generated pandas code in the restricted sandbox against the session's DataFrame | `code: str`, `df: pd.DataFrame`, `timeout_s: float` | `SandboxResult{result_repr: str \| None, stdout: str, error: str \| None}` | None (pure computation on an in-memory copy of `df`; no filesystem/network access) |

**Tool selection strategy:** not LLM tool-calling in the Anthropic tool-use sense — the graph itself always calls `run_pandas_code` exactly once per `execute_code` node visit; there is only one tool, so no routing/selection decision exists.

**Tool failure handling:** any exception raised by the generated code (or a timeout) is caught inside `run_pandas_code` and returned as `SandboxResult.error` — never raised up through the graph. The `critique` node treats a populated `error` as strong (but not automatic) evidence for `"retry"`.

---

## Agent State

```python
class AgentState(TypedDict, total=False):
    # Identity
    run_id: str                          # set at initialisation (AnalysisRunRow id)
    session_id: str                      # which session's DataFrame/history to use

    # Input
    question: str                        # the user's plain-language question
    columns: list[str]                   # session DataFrame column names (loaded by load_context)
    dtypes: dict[str, str]                # column -> pandas dtype string
    df_preview: str                      # head(5) rendered as text, for prompting only
    history: list[dict]                  # prior turns: [{"role": "user"|"assistant", "content": str}, ...]

    # Pipeline data (populated progressively by nodes)
    code: str | None                     # latest LLM-written pandas snippet
    exec_result_repr: str | None         # truncated repr() of the `result` variable
    exec_stdout: str | None              # captured stdout from the sandbox run
    exec_error: str | None               # sandbox/exception message, if any
    critique_verdict: str | None         # "confident" | "retry" | "unanswerable"
    critique_feedback: str | None        # LLM's reasoning, fed back into the next write_code call
    iteration: int                       # attempts so far, starts at 1
    max_iterations: int                  # bound, set at initialisation (default 3)
    confident: bool                      # True if critique_verdict == "confident"

    # Output
    answer: str | None                   # final plain-language answer text

    # Control
    error: str | None                    # set by any node on a FATAL (non-user-facing) failure
    status: str                          # "completed" | "failed", set by finalize/handle_error
```

Note: the DataFrame itself is never placed in `AgentState` (not JSON-loggable, and large). Nodes that need it look it up from the session store via `session_id`; only lightweight schema/preview text travels through graph state.

---

## Nodes / Steps

### `load_context`

**Reads from state:** `session_id`, `question`

**Writes to state:** `columns`, `dtypes`, `df_preview`, `history`, `iteration` (init to 1), `max_iterations` (init to 3)

**LLM call:** no

**External calls:**

| System | Operation | On Failure |
|--------|-----------|------------|
| Session store | look up `session_id` → DataFrame + message history | fatal — session missing/expired sets `error` = "Session not found. Please re-upload your CSV." and routes to `handle_error` |

**Behaviour:** Loads the session's DataFrame schema (columns, dtypes) and a small `head(5)` text preview, plus prior chat turns, into state. This is the only node that touches the session store for read purposes; it never mutates the DataFrame.

---

### `write_code`

**Reads from state:** `question`, `columns`, `dtypes`, `df_preview`, `history`, `code` (if iterating), `exec_error`, `critique_feedback`, `iteration`

**Writes to state:** `code`

**LLM call:** yes — `claude-sonnet-4-6`, prompt `src/prompts/write_code.md`. Includes the question, schema, preview rows, prior chat turns (for follow-up questions like "and the average?"), and — on retry — the previous code plus `exec_error`/`critique_feedback` so the model corrects course. Output format: a single fenced ```python block whose last statement assigns the answer to a variable named `result`; no explanation text outside the block.

**External calls:**

| System | Operation | On Failure |
|--------|-----------|------------|
| Anthropic API | generate pandas code | fatal — sets `error` and routes to `handle_error` |

**Behaviour:** Produces one candidate pandas snippet per call. On the first pass this is a fresh attempt; on a retry pass it is a corrected attempt informed by why the previous one failed or was judged insufficient.

---

### `execute_code`

**Reads from state:** `session_id`, `code`

**Writes to state:** `exec_result_repr`, `exec_stdout`, `exec_error`

**LLM call:** no

**External calls:**

| System | Operation | On Failure |
|--------|-----------|------------|
| Sandbox (`run_pandas_code`) | execute `code` against a copy of the session's DataFrame, bounded by `AGENT_SANDBOX_TIMEOUT_S` | non-fatal for user-code errors (caught, stored in `exec_error`, flows to `critique`); fatal only if the sandbox harness itself raises unexpectedly (e.g. cannot obtain the DataFrame) — sets `error` and routes to `handle_error` |

**Behaviour:** Looks up the session's DataFrame, hands a `.copy()` and the generated `code` to the sandbox, and stores whatever comes back (a result, stdout, or an error) without judging it — judgement is `critique`'s job.

---

### `critique`

**Reads from state:** `question`, `code`, `exec_result_repr`, `exec_stdout`, `exec_error`, `iteration`, `max_iterations`

**Writes to state:** `critique_verdict`, `critique_feedback`, `confident`

**LLM call:** yes — `claude-haiku-4-5-20251001`, prompt `src/prompts/critique.md`. Given the question, the code, and the execution outcome, returns strict JSON `{"verdict": "confident"|"retry"|"unanswerable", "feedback": "..."}`. `unanswerable` is reserved for cases where the code correctly reveals the question cannot be answered from this data (e.g. `exec_error` is a `KeyError` for a column absent from `columns`, or the question asks for data the schema doesn't contain) — not merely "code failed once."

**External calls:**

| System | Operation | On Failure |
|--------|-----------|------------|
| Anthropic API | judge the execution outcome | fatal — sets `error` and routes to `handle_error` (rare; a parse failure of the JSON response is handled locally as `"retry"`, not treated as fatal) |

**Behaviour:** The single self-correction checkpoint (Reflection pattern). Decides whether the loop is done (confident or genuinely unanswerable) or must attempt again, and — if retrying — carries forward concrete feedback the next `write_code` call can act on.

---

### `compose_answer`

**Reads from state:** `question`, `critique_verdict`, `critique_feedback`, `exec_result_repr`, `history`

**Writes to state:** `answer`

**LLM call:** yes — `claude-sonnet-4-6`, prompt `src/prompts/compose_answer.md`. If `critique_verdict == "confident"`, composes one plain-language paragraph embedding the real numbers from `exec_result_repr`. If `critique_verdict == "unanswerable"` (including "gave up after `max_iterations`"), composes a plain, honest "I don't have enough information/context to answer that" style response referencing why (e.g. the missing column), never inventing a number.

**External calls:**

| System | Operation | On Failure |
|--------|-----------|------------|
| Anthropic API | compose final prose | fatal — sets `error` and routes to `handle_error` |

**Behaviour:** The only node whose output the user ever sees. It never surfaces `code`, `exec_stdout`, or intermediate critique text — those stay server-side.

---

### `finalize`

**Reads from state:** `answer`, `session_id`, `question`

**Writes to state:** `status = "completed"`

**LLM call:** no

**External calls:**

| System | Operation | On Failure |
|--------|-----------|------------|
| Session store | append `{role: "assistant", content: answer}` to the session's `messages` | non-fatal — logged, response still returned (chat history for *this* turn may be missing from later prompts, but the current answer is not lost) |
| SQLite (`analysis_runs`) | write `AnalysisRunRow(status="completed", question, answer)` | non-fatal — logged and continue (observability-only write) |

**Behaviour:** Persists the turn into the session's live chat history so the next question can reference it, and writes the observability record.

---

### `handle_error`

**Reads from state:** `error`, `run_id`, `question`

**Writes to state:** `status = "failed"`

**LLM call:** no

**External calls:**

| System | Operation | On Failure |
|--------|-----------|------------|
| SQLite (`analysis_runs`) | write `AnalysisRunRow(status="failed", error_message=error)` | non-fatal — logged only, does not block returning the error to the API caller |

**Behaviour:** Reserved for genuinely fatal, non-user-facing failures (missing session, LLM API down, sandbox harness crash) — distinct from "the question is unanswerable," which is a normal `compose_answer` outcome, not an error. The API layer turns `state["error"]` into a structured error response (never a raw 500), per `harness/patterns/code.md`'s "render an error page, don't raise" convention adapted to a JSON API (`api_error(...)`).

---

## Graph / Flow Topology

```
START
  │
  ▼
load_context ──(session missing)──► handle_error ──► END
  │
  ▼
write_code ──(LLM error)──► handle_error
  │
  ▼
execute_code ──(sandbox harness crash)──► handle_error
  │
  ▼
critique ──(LLM error)──► handle_error
  │
  ├──(verdict == "confident")────────────────────┐
  ├──(verdict == "unanswerable")──────────────────┤
  ├──(verdict == "retry" AND iteration < max)──► write_code   (iteration += 1)
  └──(verdict == "retry" AND iteration >= max)────┘
                                                    ▼
                                              compose_answer ──(LLM error)──► handle_error
                                                    │
                                                    ▼
                                                finalize ──► END
```

**Conditional edges:**

| Source node | Condition | Target |
|-------------|-----------|--------|
| `load_context` | `state.get("error")` is set | `handle_error` |
| `load_context` | no error | `write_code` |
| `write_code` | `state.get("error")` is set | `handle_error` |
| `write_code` | no error | `execute_code` |
| `execute_code` | `state.get("error")` is set (harness crash, not user-code error) | `handle_error` |
| `execute_code` | no error | `critique` |
| `critique` | `state.get("error")` is set | `handle_error` |
| `critique` | `critique_verdict in ("confident", "unanswerable")` | `compose_answer` |
| `critique` | `critique_verdict == "retry"` and `iteration < max_iterations` | `write_code` |
| `critique` | `critique_verdict == "retry"` and `iteration >= max_iterations` | `compose_answer` (treated as `unanswerable`-equivalent for prose purposes) |
| `compose_answer` | `state.get("error")` is set | `handle_error` |
| `compose_answer` | no error | `finalize` |

---

## Memory & Context

| Scope | Mechanism | What is stored |
|-------|-----------|----------------|
| **Within a run (one question)** | LangGraph state | The question, schema, code attempts, execution outcomes, critique verdicts for that single question |
| **Across questions (a session)** | In-memory `SessionStore` (`src/session/store.py`) | The uploaded DataFrame and the full `messages` list (`{role, content}` per turn) for the life of the browser tab / process |
| **Across server restarts** | None (by design) | Nothing — matches the product brief; no session/history persistence is required beyond the live session |
| **Conversation** | `history` field, populated from `SessionStore.messages` by `load_context` and passed into `write_code` and `compose_answer` prompts | Prior user questions and assistant answers, so follow-ups ("and the average?") resolve using earlier context |

**Context window management:** `history` is passed in full (uncompressed) in Phase 1 — sessions are short-lived, single-file, personal-use, so turn counts are expected to be small enough that this never approaches the context window. If this becomes a problem, a Phase 2 candidate is a sliding window (last N turns) or summarization; not needed for Phase 1.

---

## Error Handling & Recovery

**Node-level:** every node wraps its external call (LLM or sandbox) in try/except; a caught exception sets `state["error"]` to a human-readable message and lets the conditional edge route to `handle_error`. Sandbox/user-code errors are the one exception to this — they are expected and are captured as data (`exec_error`) for `critique` to reason about, not treated as fatal.

**Graph-level (`handle_error` node):**
- Reads: `state.error`, `state.run_id`
- Writes: `AnalysisRunRow.status = "failed"`, `error_message = state.error`
- Logs the error with `run_id` and `session_id` context (structured log)
- Terminates the graph; the API returns a structured error envelope (`api_error(...)`), never a bare 500

**Resume / retry strategy:** no cross-request resume/checkpointing in Phase 1 — each chat message is one synchronous graph invocation; if it fails fatally, the user simply asks the question again (the session's DataFrame and prior history are untouched by a failed run).

**Partial failure:** the two non-critical writes in `finalize`/`handle_error` (session history append, `analysis_runs` log write) are best-effort — a failure there is logged but never blocks returning the answer/error to the user, since neither is required for the current response to be correct.

---

## Observability

| Signal | What | Where |
|--------|------|-------|
| **Trace** | One trace per chat question, one span per node (`load_context`, `write_code`, `execute_code`, `critique`, `compose_answer`, `finalize`/`handle_error`) | LangSmith (`LANGCHAIN_TRACING_V2=true`, `LANGCHAIN_API_KEY` from `.env`) |
| **LLM calls** | Prompt, completion, tokens, latency, model, per node | LangSmith + structured `structlog` line to stdout (`event="llm_call", node=..., model=..., latency_ms=...`) |
| **Sandbox execution** | Code (attempt only, never logged to the DB, only to structured stdout logs for local debugging), success/error, latency, attempt number | Structured log (`event="sandbox_exec", attempt=iteration, error=exec_error, latency_ms=...`) |
| **Run outcome** | `status`, `iteration` count reached, `error` if any | `analysis_runs` table + structured log (`event="analysis_run", status=..., iterations=...`) |

This satisfies the "observability wired from day one" rule: LangSmith tracing env vars are documented in `.env.example`, and every node logs a structured line regardless of whether LangSmith is configured.

---

## Concurrency Model

- **Run isolation:** one graph invocation per HTTP request, synchronous. Concurrent chat requests against *different* `session_id`s run fully in parallel (no shared state). Concurrent requests against the *same* `session_id` are serialized by a per-session `threading.Lock` held in `SessionStore` for the duration of the graph run, preventing two questions from racing over the same in-memory DataFrame/history.
- **Parallel nodes within a run:** none — the write→execute→critique loop is inherently sequential (each step depends on the previous one's output).
- **Checkpointing:** none — no `SqliteSaver`/`PostgresSaver`; runs are short (bounded by `max_iterations` × per-call LLM latency) and there is no human-in-the-loop pause to checkpoint across.

---

## Graph Assembly (`src/graph/agent.py`)

```python
from langgraph.graph import StateGraph, END

from graph.state import AgentState
from graph.nodes import (
    load_context, write_code, execute_code, critique,
    compose_answer, finalize, handle_error,
)
from graph.edges import (
    after_load_context, after_write_code, after_execute_code,
    after_critique, after_compose_answer,
)


def _build_graph() -> StateGraph:
    g = StateGraph(AgentState)
    g.add_node("load_context", load_context)
    g.add_node("write_code", write_code)
    g.add_node("execute_code", execute_code)
    g.add_node("critique", critique)
    g.add_node("compose_answer", compose_answer)
    g.add_node("finalize", finalize)
    g.add_node("handle_error", handle_error)

    g.set_entry_point("load_context")

    g.add_conditional_edges("load_context", after_load_context,
        {"write_code": "write_code", "handle_error": "handle_error"})
    g.add_conditional_edges("write_code", after_write_code,
        {"execute_code": "execute_code", "handle_error": "handle_error"})
    g.add_conditional_edges("execute_code", after_execute_code,
        {"critique": "critique", "handle_error": "handle_error"})
    g.add_conditional_edges("critique", after_critique,
        {"write_code": "write_code", "compose_answer": "compose_answer", "handle_error": "handle_error"})
    g.add_conditional_edges("compose_answer", after_compose_answer,
        {"finalize": "finalize", "handle_error": "handle_error"})

    g.add_edge("finalize", END)
    g.add_edge("handle_error", END)
    return g.compile()


agentic_ai = _build_graph()
```

`after_critique` encapsulates the retry bound: `if state.get("error"): return "handle_error"`; `elif state["critique_verdict"] == "retry" and state["iteration"] < state["max_iterations"]: state["iteration"] += 1; return "write_code"`; `else: return "compose_answer"`.
