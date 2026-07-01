from graph.nodes import MAX_REFINES
from graph.state import AgentState


def route_after_triage(state: AgentState) -> str:
    """needs_clarification -> clarify (END, return question); else -> plan."""
    return "clarify" if state.get("needs_clarification") else "plan"


def route_after_plan(state: AgentState) -> str:
    return "handle_error" if state.get("error") else "write_code"


def route_after_execute(state: AgentState) -> str:
    """ok -> answer; error & under cap -> refine; error & at cap -> answer (best-effort)."""
    if state.get("error"):
        return "handle_error"
    exec_result = state.get("exec_result") or {}
    if exec_result.get("ok"):
        return "answer"
    if state.get("refine_count", 0) < MAX_REFINES:
        return "refine"
    return "answer"
