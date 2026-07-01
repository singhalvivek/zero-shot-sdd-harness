"""Run an ask against a session: load context, run the graph, persist results.

Provides:
  - run_ask(session_id, question)            -> dict   (non-streaming, for tests/integration)
  - stream_ask(session_id, question)         -> async generator of SSE event dicts

Both share _prepare_state (load session + datasets + prior messages, schema-only)
and _persist (Message rows + AuditLog update). The streaming path reuses the
graph node functions for plan/write_code/execute/refine, then streams the answer
token-by-token via LLMClient.stream_model.
"""
from __future__ import annotations

import asyncio
import json
import time
from collections.abc import AsyncIterator

from db.models import AuditLog, Dataset, Message, Session, SessionDataset
from db.session import create_db_session
from graph.agent import agentic_ai
from graph.nodes import (
    MAX_REFINES,
    generate_suggestions,
    node_execute,
    node_plan,
    node_refine,
    node_triage,
    node_write_code,
)
from graph.prompting import build_answer_prompt, load_prompt
from graph.state import AgentState
from llm.client import LLMClient
from observability.events import get_logger

_log = get_logger("runner")


class SessionNotFound(Exception):
    pass


class NoDatasetBound(Exception):
    pass


def _load_schemas_and_paths(session: Session, session_id: str) -> tuple[dict, dict]:
    binds = (
        session.query(SessionDataset)
        .filter(SessionDataset.session_id == session_id)
        .all()
    )
    schemas: dict[str, dict] = {}
    paths: dict[str, str] = {}
    for bind in binds:
        ds = session.get(Dataset, bind.dataset_id)
        if ds is None:
            continue
        schema = json.loads(ds.schema_json)
        schemas[ds.df_name] = schema
        paths[ds.df_name] = ds.file_path
    return schemas, paths


def _load_messages(session: Session, session_id: str) -> list:
    rows = (
        session.query(Message)
        .filter(Message.session_id == session_id)
        .order_by(Message.created_at.asc())
        .all()
    )
    return [{"role": r.role, "content": r.content} for r in rows]


def _prepare(session_id: str, question: str) -> tuple[AgentState, str]:
    """Validate + build the initial state and create the AuditLog row.

    Persists the USER Message turn EARLY (in the same transaction that creates the
    AuditLog row) so a session that is resumed while the answer is still streaming
    always shows the question turn — the assistant turn is written later, once the
    answer is known (see ``_persist``). This avoids the resume-loses-the-turn race
    where persistence happened only after the ~9s stream completed.

    Returns (state, run_id). Raises SessionNotFound / NoDatasetBound / ValueError.
    """
    if not question or not question.strip():
        raise ValueError("question must not be empty")

    from datetime import datetime, timezone

    with create_db_session() as session:
        sess = session.get(Session, session_id)
        if sess is None:
            raise SessionNotFound(session_id)

        schemas, paths = _load_schemas_and_paths(session, session_id)
        if not paths:
            raise NoDatasetBound(session_id)

        # Load prior history BEFORE writing this turn's user row so state.messages
        # reflects the conversation up to (not including) the current question.
        messages = _load_messages(session, session_id)

        audit = AuditLog(session_id=session_id, question=question, status="running")
        session.add(audit)
        session.flush()
        run_id = audit.id

        # Early user-turn persist: the question is resumable immediately.
        session.add(Message(session_id=session_id, role="user", content=question))

        # Advance updated_at now so the switcher surfaces the active session, and
        # seed the title from the first question if not already set.
        sess.updated_at = datetime.now(timezone.utc)
        if not sess.title:
            sess.title = question[:80]

    state: AgentState = {
        "run_id": run_id,
        "session_id": session_id,
        "question": question,
        "dataset_paths": paths,
        "schemas": schemas,
        "messages": messages,
        "refine_count": 0,
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "error": None,
    }
    return state, run_id


def _persist(state: AgentState, status: str) -> None:
    """Finalize a run: write the ASSISTANT turn (if any) and update the AuditLog.

    The USER Message turn was already written early in ``_prepare`` — this is
    called once the answer is known (right when the stream emits ``done``, or at
    the end of the non-streaming ``run_ask``). It NEVER writes the user row again,
    so there is exactly one user turn per ask. On the clarify path no assistant
    row is written; on the error path the state carries a user-facing message so
    an assistant row is written for it.
    """
    run_id = state["run_id"]
    session_id = state["session_id"]
    answer = state.get("answer_text")
    with create_db_session() as session:
        if answer:
            session.add(Message(session_id=session_id, role="assistant", content=answer))
        audit = session.get(AuditLog, run_id)
        if audit is not None:
            audit.answer = answer
            audit.prompt_tokens = state.get("prompt_tokens", 0)
            audit.completion_tokens = state.get("completion_tokens", 0)
            audit.status = status
            audit.error_message = state.get("error")
        # Touch the session so updated_at advances on completion (keeps newest-first
        # ordering fresh). onupdate fires only on a real change, so set explicitly.
        from datetime import datetime, timezone

        sess = session.get(Session, session_id)
        if sess is not None:
            sess.updated_at = datetime.now(timezone.utc)


def run_ask(session_id: str, question: str) -> dict:
    """Non-streaming end-to-end ask. Returns the final state-ish dict."""
    started = time.monotonic()
    state, run_id = _prepare(session_id, question)
    final: AgentState = agentic_ai.invoke(state)
    if final.get("needs_clarification"):
        status = "needs_clarification"
    else:
        status = final.get("status", "completed")
    _persist(final, status)
    _log.info(
        "ask.complete",
        run_id=run_id,
        status=status,
        latency_ms=int((time.monotonic() - started) * 1000),
        prompt_tokens=final.get("prompt_tokens"),
        completion_tokens=final.get("completion_tokens"),
    )
    return {
        "run_id": run_id,
        "status": status,
        "answer_text": final.get("answer_text", ""),
        "suggestions": final.get("suggestions", []),
        "needs_clarification": bool(final.get("needs_clarification")),
        "clarifying_question": final.get("clarifying_question"),
        "prompt_tokens": final.get("prompt_tokens", 0),
        "completion_tokens": final.get("completion_tokens", 0),
        "exec_result": final.get("exec_result"),
        "error": final.get("error"),
    }


def _run_until_execute(state: AgentState) -> AgentState:
    """Run triage -> plan -> write_code -> (execute <-> refine) using the node funcs.

    If triage flags ambiguity, returns early with needs_clarification set; the
    caller must NOT run analysis in that case.
    """
    state = node_triage(state)
    if state.get("needs_clarification"):
        return state
    state = node_plan(state)
    if state.get("error"):
        return state
    state = node_write_code(state)
    if state.get("error"):
        return state
    while True:
        state = node_execute(state)
        if state.get("error"):
            return state
        exec_result = state.get("exec_result") or {}
        if exec_result.get("ok"):
            return state
        if state.get("refine_count", 0) >= MAX_REFINES:
            return state
        state = node_refine(state)
        if state.get("error"):
            return state


_STREAM_DONE = object()  # sentinel marking exhaustion of the sync token generator


def _open_answer_stream(prompt: str):
    """Construct the blocking Gemini streaming iterator (runs in a worker thread).

    The gRPC/absl-backed google-genai client MUST NOT be exercised on the asyncio
    event-loop thread: creating the client + starting the streaming RPC spawns
    background threads, and any subsequent subprocess spawn on the loop thread in
    that state triggers a native fork/spawn-after-threads abort (no Python
    traceback). Every touch of the client is therefore confined to worker threads
    via asyncio.to_thread.
    """
    return LLMClient().stream_model(prompt, system=load_prompt("answer"))


async def stream_ask(session_id: str, question: str) -> AsyncIterator[dict]:
    """Async generator yielding SSE event dicts: token / usage / done / error.

    Validation errors are raised BEFORE streaming starts (so the endpoint can
    return 4xx). Errors during the run are emitted as an `error` event.

    CRITICAL: all blocking / subprocess-spawning / gRPC work is dispatched to
    worker threads via ``asyncio.to_thread`` so nothing runs on the event-loop
    thread. ``_run_until_execute`` spawns a pandas subprocess (native spawn) and
    the answer step iterates the blocking Gemini gRPC generator; running either
    inline on the loop thread crashed the process on the 2nd ask in a session.
    """
    state, run_id = _prepare(session_id, question)  # may raise -> 4xx at endpoint

    try:
        # triage -> plan -> write_code -> (execute <-> refine); execute spawns a
        # pandas subprocess, so it must run off the event-loop thread.
        state = await asyncio.to_thread(_run_until_execute, state)

        if state.get("needs_clarification"):
            cq = state.get("clarifying_question") or "Could you clarify your question?"
            state["status"] = "needs_clarification"
            state["answer_text"] = None
            await asyncio.to_thread(_persist, state, "needs_clarification")
            yield {"event": "clarify", "data": {"question": cq}}
            yield {
                "event": "done",
                "data": {"run_id": run_id, "status": "needs_clarification"},
            }
            return

        if state.get("error"):
            state["status"] = "failed"
            msg = "Sorry, I couldn't complete that analysis. Please try rephrasing."
            state["answer_text"] = msg
            await asyncio.to_thread(_persist, state, "failed")
            yield {"event": "error", "data": {"message": state["error"]}}
            yield {"event": "token", "data": {"text": msg}}
            yield {"event": "done", "data": {"run_id": run_id, "status": "failed"}}
            return

        exec_result = state.get("exec_result") or {}
        result_repr = exec_result.get("result_repr") or exec_result.get("error") or "(no result)"
        prompt = build_answer_prompt(question, result_repr, state.get("messages"))

        # Build the blocking Gemini generator on a worker thread, then pull each
        # chunk off-thread so the gRPC iteration never runs on the event loop.
        stream_it = await asyncio.to_thread(_open_answer_stream, prompt)

        parts: list[str] = []
        usage = {"prompt_tokens": 0, "completion_tokens": 0}
        while True:
            chunk = await asyncio.to_thread(next, stream_it, _STREAM_DONE)
            if chunk is _STREAM_DONE:
                break
            if "text" in chunk:
                parts.append(chunk["text"])
                yield {"event": "token", "data": {"text": chunk["text"]}}
            elif "usage" in chunk:
                usage = chunk["usage"]

        state["answer_text"] = "".join(parts)
        state["prompt_tokens"] = state.get("prompt_tokens", 0) + usage["prompt_tokens"]
        state["completion_tokens"] = state.get("completion_tokens", 0) + usage["completion_tokens"]

        # One extra non-streaming Gemini call for follow-up suggestions
        # (best-effort, also off the loop thread).
        sug = await asyncio.to_thread(generate_suggestions, state)
        state["suggestions"] = sug["suggestions"]
        state["prompt_tokens"] += sug["usage"]["prompt_tokens"]
        state["completion_tokens"] += sug["usage"]["completion_tokens"]

        state["status"] = "completed"
        await asyncio.to_thread(_persist, state, "completed")

        yield {"event": "suggestions", "data": {"items": state["suggestions"]}}
        yield {
            "event": "usage",
            "data": {
                "prompt_tokens": state["prompt_tokens"],
                "completion_tokens": state["completion_tokens"],
            },
        }
        yield {"event": "done", "data": {"run_id": run_id, "status": "completed"}}
    except Exception as exc:  # noqa: BLE001
        state["error"] = str(exc)
        state["status"] = "failed"
        await asyncio.to_thread(_persist, state, "failed")
        _log.error("ask.stream_error", run_id=run_id, error=str(exc))
        yield {"event": "error", "data": {"message": str(exc)}}
        yield {"event": "done", "data": {"run_id": run_id, "status": "failed"}}
