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


def test_route_after_triage():
    from graph.edges import route_after_triage
    assert route_after_triage({}) == "plan"
    assert route_after_triage({"needs_clarification": False}) == "plan"
    assert route_after_triage({"needs_clarification": True}) == "clarify"


def test_triage_is_entry_point():
    """Graph entry point is triage (Phase-2 topology change)."""
    from graph.agent import agentic_ai
    # langgraph wires the entry point as an edge from START ("__start__").
    assert "triage" in agentic_ai.nodes


def test_parse_triage_clear_and_ambiguous():
    from graph.nodes import parse_triage
    assert parse_triage('{"clear": true}') == (True, None)
    clear, q = parse_triage('{"clear": false, "question": "By which metric?"}')
    assert clear is False
    assert q == "By which metric?"
    # malformed -> conservative pass-through
    assert parse_triage("not json at all") == (True, None)
    # fenced JSON still parses
    assert parse_triage('```json\n{"clear": true}\n```') == (True, None)


def test_parse_suggestions():
    from graph.nodes import parse_suggestions
    items = parse_suggestions('["A?", "B?", "C?", "D?"]')
    assert items == ["A?", "B?", "C?"]  # capped at 3
    assert parse_suggestions("garbage") == []
    assert parse_suggestions('```json\n["X?", "Y?"]\n```') == ["X?", "Y?"]
