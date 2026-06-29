"""Graph nodes for the data-analysis agent.

Each node wraps its body in try/except; a fatal error sets state['error'] so the
graph routes to handle_error. LLM calls go through LLMClient (real provider via
.env). Prompts are schema-only (see graph.prompting privacy guard).
"""
from __future__ import annotations

import json
import re

from graph.prompting import (
    build_answer_prompt,
    build_plan_prompt,
    build_refine_prompt,
    build_suggestions_prompt,
    build_triage_prompt,
    build_write_code_prompt,
    extract_python,
    load_prompt,
)
from graph.state import AgentState
from llm.client import LLMClient
from observability.events import get_logger

MAX_REFINES = 3

_log = get_logger("graph")


def _accumulate_tokens(state: AgentState, usage: dict) -> dict:
    return {
        "prompt_tokens": state.get("prompt_tokens", 0) + usage.get("prompt_tokens", 0),
        "completion_tokens": state.get("completion_tokens", 0)
        + usage.get("completion_tokens", 0),
    }


def _extract_json(text: str) -> str:
    """Strip code fences and pull the first JSON object/array out of the text."""
    t = text.strip()
    if t.startswith("```"):
        # drop opening fence (optionally with a language tag) and closing fence
        t = re.sub(r"^```[a-zA-Z]*\n?", "", t)
        t = re.sub(r"\n?```$", "", t).strip()
    return t


def parse_triage(text: str) -> tuple[bool, str | None]:
    """Parse the triage LLM output. Conservative: on any parse failure, treat as
    clear (do NOT block a normal question on a malformed signal)."""
    try:
        data = json.loads(_extract_json(text))
    except Exception:  # noqa: BLE001
        # Fallback: look for an embedded object.
        m = re.search(r"\{.*\}", text, re.DOTALL)
        if not m:
            return True, None
        try:
            data = json.loads(m.group(0))
        except Exception:  # noqa: BLE001
            return True, None
    if not isinstance(data, dict):
        return True, None
    if data.get("clear", True):
        return True, None
    question = data.get("question") or "Could you clarify what you'd like to know?"
    return False, str(question)


def parse_suggestions(text: str) -> list[str]:
    """Parse the suggestions LLM output into 2-3 strings. On failure, return []."""
    try:
        data = json.loads(_extract_json(text))
    except Exception:  # noqa: BLE001
        m = re.search(r"\[.*\]", text, re.DOTALL)
        if not m:
            return []
        try:
            data = json.loads(m.group(0))
        except Exception:  # noqa: BLE001
            return []
    if not isinstance(data, list):
        return []
    items = [str(s).strip() for s in data if str(s).strip()]
    return items[:3]


def node_triage(state: AgentState) -> AgentState:
    """Classify whether the question is answerable as-is or genuinely ambiguous.

    Conservative by design: any parse failure or LLM error falls through as clear
    so the golden analysis path is never blocked by triage.
    """
    try:
        prompt = build_triage_prompt(
            state["question"], state.get("schemas", {}), state.get("messages")
        )
        out = LLMClient().call_model_with_usage(prompt, system=load_prompt("triage"))
        clear, clarifying = parse_triage(out["text"])
        _log.info(
            "node.triage",
            run_id=state.get("run_id"),
            needs_clarification=not clear,
        )
        return {
            **state,
            "needs_clarification": not clear,
            "clarifying_question": clarifying,
            **_accumulate_tokens(state, out),
        }
    except Exception as exc:  # noqa: BLE001
        # Never block analysis on a triage failure.
        _log.error("node.triage_failed", run_id=state.get("run_id"), error=str(exc))
        return {**state, "needs_clarification": False, "clarifying_question": None}


def generate_suggestions(state: AgentState) -> dict:
    """One extra (non-streaming) LLM call to produce 2-3 follow-up suggestions,
    grounded schema-only + aggregate result. Returns {suggestions, usage}.
    Never raises — suggestions are best-effort."""
    try:
        exec_result = state.get("exec_result") or {}
        result_repr = (
            exec_result.get("result_repr") or exec_result.get("error") or "(no result)"
        )
        prompt = build_suggestions_prompt(
            state["question"], result_repr, state.get("schemas", {})
        )
        out = LLMClient().call_model_with_usage(
            prompt, system=load_prompt("suggestions")
        )
        items = parse_suggestions(out["text"])
        return {
            "suggestions": items,
            "usage": {
                "prompt_tokens": out.get("prompt_tokens", 0),
                "completion_tokens": out.get("completion_tokens", 0),
            },
        }
    except Exception as exc:  # noqa: BLE001
        _log.error("node.suggestions_failed", run_id=state.get("run_id"), error=str(exc))
        return {"suggestions": [], "usage": {"prompt_tokens": 0, "completion_tokens": 0}}


def node_plan(state: AgentState) -> AgentState:
    try:
        prompt = build_plan_prompt(
            state["question"], state.get("schemas", {}), state.get("messages")
        )
        out = LLMClient().call_model_with_usage(prompt, system=load_prompt("plan"))
        _log.info("node.plan", run_id=state.get("run_id"))
        return {**state, "plan": out["text"], **_accumulate_tokens(state, out)}
    except Exception as exc:  # noqa: BLE001
        return {**state, "error": f"plan failed: {exc}"}


def node_write_code(state: AgentState) -> AgentState:
    try:
        prompt = build_write_code_prompt(
            state["question"], state.get("plan", ""), state.get("schemas", {})
        )
        out = LLMClient().call_model_with_usage(prompt, system=load_prompt("write_code"))
        code = extract_python(out["text"])
        _log.info("node.write_code", run_id=state.get("run_id"))
        return {**state, "code": code, **_accumulate_tokens(state, out)}
    except Exception as exc:  # noqa: BLE001
        return {**state, "error": f"write_code failed: {exc}"}


def node_execute(state: AgentState) -> AgentState:
    try:
        from analysis.sandbox import run_pandas

        result = run_pandas(state.get("code", ""), state.get("dataset_paths", {}))
        _log.info(
            "node.execute",
            run_id=state.get("run_id"),
            ok=result.get("ok"),
            refine_count=state.get("refine_count", 0),
        )
        return {**state, "exec_result": result}
    except Exception as exc:  # noqa: BLE001
        return {**state, "error": f"execute failed: {exc}"}


def node_refine(state: AgentState) -> AgentState:
    try:
        err = (state.get("exec_result") or {}).get("error", "")
        prompt = build_refine_prompt(
            state["question"],
            state.get("plan", ""),
            state.get("code", ""),
            err,
            state.get("schemas", {}),
        )
        out = LLMClient().call_model_with_usage(prompt, system=load_prompt("refine"))
        code = extract_python(out["text"])
        new_count = state.get("refine_count", 0) + 1
        _log.info("node.refine", run_id=state.get("run_id"), refine_count=new_count)
        return {**state, "code": code, "refine_count": new_count, **_accumulate_tokens(state, out)}
    except Exception as exc:  # noqa: BLE001
        return {**state, "error": f"refine failed: {exc}"}


def node_answer(state: AgentState) -> AgentState:
    """Non-streaming answer (used by the graph + non-streaming runner).

    The streaming runner streams the same prompt token-by-token instead.
    """
    try:
        exec_result = state.get("exec_result") or {}
        result_repr = exec_result.get("result_repr") or exec_result.get("error") or "(no result)"
        prompt = build_answer_prompt(state["question"], result_repr, state.get("messages"))
        out = LLMClient().call_model_with_usage(prompt, system=load_prompt("answer"))
        state = {**state, "answer_text": out["text"], **_accumulate_tokens(state, out)}
        _log.info("node.answer", run_id=state.get("run_id"))
        sug = generate_suggestions(state)
        return {
            **state,
            "suggestions": sug["suggestions"],
            **_accumulate_tokens(state, sug["usage"]),
        }
    except Exception as exc:  # noqa: BLE001
        return {**state, "error": f"answer failed: {exc}"}


def node_finalize(state: AgentState) -> AgentState:
    return {**state, "status": "completed"}


def node_handle_error(state: AgentState) -> AgentState:
    _log.error("node.handle_error", run_id=state.get("run_id"), error=state.get("error"))
    return {
        **state,
        "status": "failed",
        "answer_text": state.get("answer_text")
        or "Sorry, I couldn't complete that analysis. Please try rephrasing your question.",
    }
