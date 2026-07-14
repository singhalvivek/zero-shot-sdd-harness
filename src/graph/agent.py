from langgraph.graph import END, StateGraph

from graph.edges import after_execute, after_generate, after_safety, entry_route
from graph.nodes import (
    execute_cadquery,
    export_model,
    finalize,
    generate_code,
    handle_error,
    repair_on_error,
    static_safety_check,
)
from graph.state import AgentState


def _build_graph():
    g = StateGraph(AgentState)
    for name, fn in [
        ("generate_code", generate_code),
        ("static_safety_check", static_safety_check),
        ("execute_cadquery", execute_cadquery),
        ("repair_on_error", repair_on_error),
        ("export_model", export_model),
        ("finalize", finalize),
        ("handle_error", handle_error),
    ]:
        g.add_node(name, fn)

    g.set_conditional_entry_point(
        entry_route,
        {
            "generate_code": "generate_code",
            "static_safety_check": "static_safety_check",
        },
    )
    g.add_conditional_edges(
        "generate_code",
        after_generate,
        {"static_safety_check": "static_safety_check", "handle_error": "handle_error"},
    )
    g.add_conditional_edges(
        "static_safety_check",
        after_safety,
        {"execute_cadquery": "execute_cadquery", "handle_error": "handle_error"},
    )
    g.add_conditional_edges(
        "execute_cadquery",
        after_execute,
        {
            "export_model": "export_model",
            "repair_on_error": "repair_on_error",
            "handle_error": "handle_error",
        },
    )
    g.add_edge("repair_on_error", "static_safety_check")
    g.add_edge("export_model", "finalize")
    g.add_edge("finalize", END)
    g.add_edge("handle_error", END)
    return g.compile()


agentic_ai = _build_graph()
