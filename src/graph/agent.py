"""Graph assembly for the data-analysis agent.

Phase 1 compiles WITHOUT a checkpointer. The SqliteSaver checkpointer (spec
agent.md) exists primarily for the Phase-2 clarify interrupt and is deferred to
keep the Phase-1 streaming path simple; conversation continuity in P1 is provided
by rehydrating prior Message rows in the runner (graph.runner). This is a
documented, intentional P1 simplification.
"""
from langgraph.graph import END, StateGraph

from graph.edges import route_after_execute, route_after_plan
from graph.nodes import (
    node_answer,
    node_execute,
    node_finalize,
    node_handle_error,
    node_plan,
    node_refine,
    node_write_code,
)
from graph.state import AgentState


def _build_graph():
    g = StateGraph(AgentState)

    g.add_node("plan", node_plan)
    g.add_node("write_code", node_write_code)
    g.add_node("execute", node_execute)
    g.add_node("refine", node_refine)
    g.add_node("answer", node_answer)
    g.add_node("finalize", node_finalize)
    g.add_node("handle_error", node_handle_error)

    g.set_entry_point("plan")

    g.add_conditional_edges(
        "plan", route_after_plan, {"write_code": "write_code", "handle_error": "handle_error"}
    )
    g.add_edge("write_code", "execute")
    g.add_conditional_edges(
        "execute",
        route_after_execute,
        {"answer": "answer", "refine": "refine", "handle_error": "handle_error"},
    )
    g.add_edge("refine", "execute")
    g.add_edge("answer", "finalize")
    g.add_edge("finalize", END)
    g.add_edge("handle_error", END)

    return g.compile()


agentic_ai = _build_graph()
