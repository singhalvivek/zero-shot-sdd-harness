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

import json
import time
from collections.abc import AsyncIterator

from db.models import AuditLog, Dataset, Message, Session, SessionDataset
from db.session import create_db_session
from graph.agent import agentic_ai
from graph.nodes import (
    MAX_REFINES,
    node_execute,
    node_plan,
    node_refine,
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

    Returns (state, run_id). Raises SessionNotFound / NoDatasetBound / ValueError.
    """
    if not question or not question.strip():
        raise ValueError("question must not be empty")

    with create_db_session() as session:
        sess = session.get(Session, session_id)
        if sess is None:
            raise SessionNotFound(session_id)

        schemas, paths = _load_schemas_and_paths(session, session_id)
        if not paths:
            raise NoDatasetBound(session_id)

        messages = _load_messages(session, session_id)

        audit = AuditLog(session_id=session_id, question=question, status="running")
        session.add(audit)
        session.flush()
        run_id = audit.id

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
    run_id = state["run_id"]
    session_id = state["session_id"]
    answer = state.get("answer_text")
    with create_db_session() as session:
        session.add(Message(session_id=session_id, role="user", content=state["question"]))
        if answer:
            session.add(Message(session_id=session_id, role="assistant", content=answer))
        audit = session.get(AuditLog, run_id)
        if audit is not None:
            audit.answer = answer
            audit.prompt_tokens = state.get("prompt_tokens", 0)
            audit.completion_tokens = state.get("completion_tokens", 0)
            audit.status = status
            audit.error_message = state.get("error")


def run_ask(session_id: str, question: str) -> dict:
    """Non-streaming end-to-end ask. Returns the final state-ish dict."""
    started = time.monotonic()
    state, run_id = _prepare(session_id, question)
    final: AgentState = agentic_ai.invoke(state)
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
        "prompt_tokens": final.get("prompt_tokens", 0),
        "completion_tokens": final.get("completion_tokens", 0),
        "exec_result": final.get("exec_result"),
        "error": final.get("error"),
    }


def _run_until_execute(state: AgentState) -> AgentState:
    """Run plan -> write_code -> (execute <-> refine) using the node functions."""
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


async def stream_ask(session_id: str, question: str) -> AsyncIterator[dict]:
    """Async generator yielding SSE event dicts: token / usage / done / error.

    Validation errors are raised BEFORE streaming starts (so the endpoint can
    return 4xx). Errors during the run are emitted as an `error` event.
    """
    state, run_id = _prepare(session_id, question)  # may raise -> 4xx at endpoint

    try:
        state = _run_until_execute(state)

        if state.get("error"):
            state["status"] = "failed"
            msg = "Sorry, I couldn't complete that analysis. Please try rephrasing."
            state["answer_text"] = msg
            _persist(state, "failed")
            yield {"event": "error", "data": {"message": state["error"]}}
            yield {"event": "token", "data": {"text": msg}}
            yield {"event": "done", "data": {"run_id": run_id, "status": "failed"}}
            return

        exec_result = state.get("exec_result") or {}
        result_repr = exec_result.get("result_repr") or exec_result.get("error") or "(no result)"
        prompt = build_answer_prompt(question, result_repr, state.get("messages"))

        parts: list[str] = []
        usage = {"prompt_tokens": 0, "completion_tokens": 0}
        for chunk in LLMClient().stream_model(prompt, system=load_prompt("answer")):
            if "text" in chunk:
                parts.append(chunk["text"])
                yield {"event": "token", "data": {"text": chunk["text"]}}
            elif "usage" in chunk:
                usage = chunk["usage"]

        state["answer_text"] = "".join(parts)
        state["prompt_tokens"] = state.get("prompt_tokens", 0) + usage["prompt_tokens"]
        state["completion_tokens"] = state.get("completion_tokens", 0) + usage["completion_tokens"]
        state["status"] = "completed"
        _persist(state, "completed")

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
        _persist(state, "failed")
        _log.error("ask.stream_error", run_id=run_id, error=str(exc))
        yield {"event": "error", "data": {"message": str(exc)}}
        yield {"event": "done", "data": {"run_id": run_id, "status": "failed"}}
