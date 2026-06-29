"""Graph structure + routing unit tests — no env vars / no LLM required."""


def test_graph_compiles():
    """Graph compiles without requiring any env vars."""
    from graph.agent import agentic_ai
    assert agentic_ai is not None


def test_route_after_execute_ok_goes_to_answer():
    from graph.edges import route_after_execute
    state = {"exec_result": {"ok": True}, "refine_count": 0}
    assert route_after_execute(state) == "answer"


def test_route_after_execute_error_under_cap_refines():
    from graph.edges import route_after_execute
    state = {"exec_result": {"ok": False, "error": "boom"}, "refine_count": 0}
    assert route_after_execute(state) == "refine"


def test_route_after_execute_error_at_cap_answers():
    from graph.edges import route_after_execute
    from graph.nodes import MAX_REFINES
    state = {"exec_result": {"ok": False, "error": "boom"}, "refine_count": MAX_REFINES}
    assert route_after_execute(state) == "answer"


def test_route_after_execute_fatal_error_handles():
    from graph.edges import route_after_execute
    state = {"error": "fatal", "exec_result": {"ok": False}, "refine_count": 0}
    assert route_after_execute(state) == "handle_error"


def test_route_after_plan():
    from graph.edges import route_after_plan
    assert route_after_plan({}) == "write_code"
    assert route_after_plan({"error": "x"}) == "handle_error"
