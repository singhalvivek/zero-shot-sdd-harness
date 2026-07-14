# Agent

> The `generate_part` pipeline is a LangGraph state machine. This file is REQUIRED (framework in use) and complete.

---

## Agent Architecture Pattern

| Pattern | Chosen |
|---------|--------|
| **Graph (LangGraph)** | ✅ |

**Chosen:** Graph (LangGraph). The pipeline is a multi-step flow with a bounded self-correction loop (generate → safety-check → execute → repair ×≤3 → export), which is exactly what conditional edges + a loop-back edge express cleanly. It reuses and replaces the skeleton's single `transform_text` graph in `src/graph/`.

---

## LLM Provider & Model

| Node | Provider | Model ID | Rationale |
|------|----------|----------|-----------|
| `generate_code` | Google Gemini (`google-genai`) | `gemini-3.5-flash` **or** `gemini-3.1-flash-lite` (per-request `model_id`) | User picks: `gemini-3.5-flash` = higher-quality geometry (default); `gemini-3.1-flash-lite` = fastest/cheapest |
| `repair_on_error` | Google Gemini | same `model_id` as the run | Repair uses the same model the user chose |

Model IDs are **passed explicitly** to `genai.Client(...).models.generate_content(model=model_id, ...)` via the existing `GeminiProvider` (constructed per-run with the chosen model), NOT the provider's hardcoded `DEFAULT_MODEL`. The key is `AGENT_GEMINI_API_KEY` from pydantic settings, passed to `genai.Client(api_key=...)`.

> **Model-id verification — DONE at scaffold (2026-07-14):** `gemini-3.5-flash` and `gemini-3.1-flash-lite` were confirmed to generate successfully against the live Gemini API with the `.env` key. The intake-requested `gemini-2.5-flash`/`-flash-lite` return 404 ("no longer available to new users") and all pro-tier ids (`gemini-2.5-pro`, `gemini-pro-latest`, `gemini-3-pro-preview`) return 429 RESOURCE_EXHAUSTED (free-tier keys have no pro quota). The runner constructs `GeminiProvider` per-request with the chosen `model_id`.

**Fallback behaviour:** Gemini unreachable / auth error / rate-limit → node sets `state["error"]`, routes to `handle_error` (HTTP 502 surfaced). No offline stub — tests call the real API with the `.env` key. A transient error may be retried once with backoff inside the provider call.

**Prompt strategy:** System instruction (in `src/prompts/generate.md`) forces: output ONLY executable CadQuery Python, no markdown/prose; assign final solid to `result`; parametric named constants at top. User message = the prompt (and, for modify, the `previous_code` block framed as "modify this"). Repair message = the failing code + the captured traceback + "return corrected code only". Markdown fences are stripped from every model output before use.

---

## Tools & Tool Calling

This graph does **not** use LLM tool-calling — nodes call helpers deterministically. The "tools" are the sandbox helpers in `src/sandbox.py`:

| Helper | Description | Inputs | Output | Side-effects |
|--------|-------------|--------|--------|--------------|
| `static_safety_check(code)` | Reject forbidden calls before exec | code str | `violation: str \| None` | none |
| `run_and_export(code, part_id, version, formats, timeout)` | Exec code in a restricted namespace **inside a child process** (Windows-safe timeout); on success export STL+STEP | code, paths, timeout | `{ok, error, stl_path, step_path}` | writes STL/STEP; spawns a process |

**Tool selection strategy:** rule-based — the graph edges decide; no LLM routing.
**Tool failure handling:** safety violation → abort (`handle_error`); exec error/timeout → repair loop (bounded).

---

## Agent State

```python
class AgentState(TypedDict, total=False):
    # Identity
    run_id: str                     # set at init (skeleton runner creates the RunRow)
    part_id: str                    # set at init: new uuid (generate) or supplied (modify/edit)
    version_number: int             # set at init: 1 (generate) or parent+1

    # Input (from the trigger)
    prompt: str                     # NL description (generate/modify); "" for edit
    previous_code: str | None       # prior version code (modify/edit); None for generate
    model_id: str                   # "gemini-3.5-flash" | "gemini-3.1-flash-lite"
    mode: str                       # "generate" | "modify" | "edit"

    # Pipeline data (populated progressively)
    generated_code: str | None      # cleaned CadQuery (fences stripped); pre-set for edit mode
    attempt_count: int              # repair attempts used so far (0..3)
    repair_attempts: list           # [{attempt, error, change_summary}]
    safety_violation: str | None    # set by static_safety_check
    exec_error: str | None          # set by execute_cadquery on failure/timeout
    token_usage: dict               # {prompt_tokens, completion_tokens, total_tokens}
    cost_usd: float

    # Output
    stl_path: str | None
    step_path: str | None
    code_path: str | None

    # Control
    error: str | None               # fatal → handle_error
    status: str                     # "completed" | "failed"
```

`MAX_REPAIR_ATTEMPTS = 3` and `EXEC_TIMEOUT_SECONDS` live as constants in `src/config/settings.py` (env-overridable). The **repair-loop bound lives in the conditional edge** `after_execute` (below), not inside a node.

---

## Nodes / Steps

### `generate_code`
- **Reads:** `prompt`, `previous_code`, `model_id`, `mode`
- **Writes:** `generated_code`, `token_usage`, `cost_usd`; or `error`
- **LLM call:** yes — Gemini with the system instruction; on `modify`, includes `previous_code`. Strips markdown fences. Computes `cost_usd` from `token_usage` × the per-model rate table.
- **External:** Gemini → on failure set `error` (fatal, routes to `handle_error`).
- **Skipped in `edit` mode** (see entry edge) — `generated_code` is pre-populated from the user's edited code.

### `static_safety_check`
- **Reads:** `generated_code`
- **Writes:** `safety_violation` + `error` if a forbidden call is found
- **LLM call:** no. Runs `sandbox.static_safety_check`. On violation → `error` set (routes to `handle_error`).

### `execute_cadquery`
- **Reads:** `generated_code`, `part_id`, `version_number`
- **Writes:** `stl_path`, `step_path` on success; `exec_error` on failure/timeout
- **LLM call:** no. Runs `sandbox.run_and_export` (restricted namespace, child-process, Windows-safe timeout). Because the CadQuery `result` object is not picklable back across the process boundary, execution **and** STL/STEP export happen together inside the sandbox call, which returns file paths or an error string.
- **External:** CadQuery/OCC → on error/timeout set `exec_error` (routes to `repair_on_error` or `handle_error` per the bound).

### `repair_on_error`
- **Reads:** `exec_error`, `generated_code`, `attempt_count`, `model_id`
- **Writes:** `generated_code` (corrected), `attempt_count += 1`, appends to `repair_attempts`; adds to `token_usage`/`cost_usd`
- **LLM call:** yes — Gemini given the failing code + traceback, returns corrected code (fences stripped). Loops back to `static_safety_check`.
- **Never entered in `edit` mode** — user-edited code is not auto-repaired.

### `export_model`
- **Reads:** `part_id`, `version_number`, `generated_code`, `stl_path`, `step_path`
- **Writes:** `code_path` (writes the versioned `.py` to `generated_code/` and `artifacts/code/`); confirms/normalizes `stl_path`/`step_path` URLs
- **LLM call:** no. STL/STEP were produced inside `execute_cadquery`'s sandbox; this node persists the source file and finalizes artifact paths/URLs. (Phase 2: also records the client-uploaded thumbnail path.)

### `finalize`
- **Reads:** all output fields
- **Writes:** `status="completed"`. The runner then commits the `parts`/`versions` rows and the run result JSON.

### `handle_error`
- **Reads:** `error` (or `safety_violation`/`exec_error`), `run_id`
- **Writes:** `status="failed"`. The runner records `runs.error_message` and the partial result (repair log, last error) so the UI can show what happened.

---

## Graph / Flow Topology

```
START
  │  (mode == "edit"? → static_safety_check : generate_code)
  ▼
generate_code ──(error)──► handle_error ──► END
  │
  ▼
static_safety_check ──(safety_violation)──► handle_error ──► END
  │
  ▼
execute_cadquery
  │        exec ok ──────────────► export_model ──► finalize ──► END
  │        exec err & attempts<3 ─► repair_on_error ─┐
  │        exec err & attempts>=3 ► handle_error ──► END
  │                                                  │
  └──────────────  repair_on_error ─────────────────┘
                     (loops back to static_safety_check)
```

**Conditional edges:**

| Source | Condition | Target |
|--------|-----------|--------|
| *entry* | `state["mode"] == "edit"` | `static_safety_check` |
| *entry* | else | `generate_code` |
| `generate_code` | `state.get("error")` | `handle_error` |
| `generate_code` | else | `static_safety_check` |
| `static_safety_check` | `state.get("error")` (violation) | `handle_error` |
| `static_safety_check` | else | `execute_cadquery` |
| `execute_cadquery` | no `exec_error` | `export_model` |
| `execute_cadquery` | `exec_error` and `attempt_count < MAX_REPAIR_ATTEMPTS` and `mode != "edit"` | `repair_on_error` |
| `execute_cadquery` | `exec_error` and (`attempt_count >= MAX_REPAIR_ATTEMPTS` or `mode == "edit"`) | `handle_error` |
| `repair_on_error` | (always) | `static_safety_check` |
| `export_model` | (always) | `finalize` |

---

## Memory & Context

| Scope | Mechanism | What is stored |
|-------|-----------|----------------|
| Within a run | LangGraph state | prompt, code, repair log, tokens, paths |
| Across runs | SQLite `parts`/`versions` + filesystem | every version's code + artifacts |
| Conversation / iteration | The **version chain**: `modify_part` loads the prior version's `code_path` content as `previous_code` (Phase 2) | the iterative "memory" — the model edits the code it produced last turn |

**Context window management:** each request carries at most one prior code file (`previous_code`) + the prompt — well within limits; no summarization needed.

> This is not a free-text chat agent, so there is no message-history memory in Phase 1. The equivalent — iterating on prior output — is the version chain, delivered by `modify_part` in Phase 2 (intake-confirmed as a secondary capability). Phase 1 is deliberately single-shot generate.

---

## Human-in-the-Loop Checkpoints

None inside the graph — the human iterates *between* runs (review the part, then modify / edit / regenerate). No mid-graph pause.

---

## Error Handling & Recovery

**Node-level:** each node wraps its work in try/except; a fatal error sets `state["error"]` (or `safety_violation`/`exec_error`) and the edge routes to `handle_error`. Exec errors are non-fatal until the repair budget is exhausted.

**Graph-level (`handle_error`):** sets `status="failed"`; the runner writes `runs.status="failed"`, `error_message`, and the partial result (repair log + last error) so the UI can explain the failure. Logs with `run_id`.

**Resume / retry:** no checkpointer — runs are short. A failed run is not resumed; the user retries (possibly with `gemini-3.1-flash-lite`).

**Partial failure:** a failed **thumbnail** upload (Phase 2) is logged and ignored (gallery shows a placeholder) — non-critical. Everything on the generate path is fatal-or-repair.

---

## Observability

| Signal | What | Where |
|--------|------|-------|
| Trace | One trace per run, one span per node | **LangSmith** when `LANGCHAIN_TRACING_V2=true` + `LANGCHAIN_API_KEY` set (env; optional, wired Phase 1) |
| LLM calls | model_id, prompt/completion tokens, cost, latency, repair attempt # | structlog JSON to stdout (existing `observability/events.py`) — **always on** |
| Exec | code length, safety result, exec ok/err, duration, timeout | structlog JSON |
| Run outcome | status, total duration, repair_count, error | DB (`runs`) + structlog |

Structured request/response logging (prompt, output, latency, error) is wired in **Phase 1** via the existing structlog config — never deferred. LangSmith is enabled if the env vars are present.

---

## Concurrency Model

- **Run isolation:** one run at a time is sufficient (single-user local app); the API processes a request synchronously. CAD execution is CPU-heavy, so serial execution avoids contention.
- **Parallel nodes within a run:** none — the pipeline is inherently sequential.
- **Sandbox process:** each `execute_cadquery` spawns exactly one short-lived child process (spawn start method, Windows-safe) that is `terminate()`d on timeout.
- **Checkpointing:** none (no long-running or human-in-the-loop pause).

---

## Graph Assembly (`src/graph/agent.py`)

```python
from langgraph.graph import StateGraph, END
from graph.state import AgentState
from graph.nodes import (
    generate_code, static_safety_check, execute_cadquery,
    repair_on_error, export_model, finalize, handle_error,
)
from graph.edges import entry_route, after_generate, after_safety, after_execute

def _build_graph():
    g = StateGraph(AgentState)
    for name, fn in [
        ("generate_code", generate_code), ("static_safety_check", static_safety_check),
        ("execute_cadquery", execute_cadquery), ("repair_on_error", repair_on_error),
        ("export_model", export_model), ("finalize", finalize), ("handle_error", handle_error),
    ]:
        g.add_node(name, fn)

    g.set_conditional_entry_point(
        entry_route,  # "static_safety_check" if edit else "generate_code"
        {"generate_code": "generate_code", "static_safety_check": "static_safety_check"},
    )
    g.add_conditional_edges("generate_code", after_generate,
        {"static_safety_check": "static_safety_check", "handle_error": "handle_error"})
    g.add_conditional_edges("static_safety_check", after_safety,
        {"execute_cadquery": "execute_cadquery", "handle_error": "handle_error"})
    g.add_conditional_edges("execute_cadquery", after_execute,
        {"export_model": "export_model", "repair_on_error": "repair_on_error", "handle_error": "handle_error"})
    g.add_edge("repair_on_error", "static_safety_check")
    g.add_edge("export_model", "finalize")
    g.add_edge("finalize", END)
    g.add_edge("handle_error", END)
    return g.compile()

agentic_ai = _build_graph()
```
