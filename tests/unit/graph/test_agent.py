"""Graph structure + edge routing — no env vars, no LLM, no API calls."""
from graph.edges import (
    after_execute,
    after_generate,
    after_safety,
    entry_route,
)


def test_graph_compiles():
    from graph.agent import agentic_ai

    assert agentic_ai is not None


def test_entry_route_generate_vs_edit():
    assert entry_route({"mode": "generate"}) == "generate_code"
    assert entry_route({"mode": "modify"}) == "generate_code"
    assert entry_route({"mode": "edit"}) == "static_safety_check"


def test_after_generate_routes_on_error():
    assert after_generate({"error": "boom"}) == "handle_error"
    assert after_generate({}) == "static_safety_check"


def test_after_safety_routes_on_violation():
    assert after_safety({"error": "safety_violation: os."}) == "handle_error"
    assert after_safety({}) == "execute_cadquery"


def test_after_execute_success_exports():
    assert after_execute({"exec_error": None}) == "export_model"


def test_after_execute_repairs_when_under_bound():
    # attempt_count 0,1,2 (< 3) → keep repairing
    for n in (0, 1, 2):
        state = {"exec_error": "traceback", "attempt_count": n, "mode": "generate"}
        assert after_execute(state) == "repair_on_error"


def test_repair_loop_bounded_at_three():
    """At attempt_count == MAX_REPAIR_ATTEMPTS (3) the loop must stop."""
    state = {"exec_error": "traceback", "attempt_count": 3, "mode": "generate"}
    assert after_execute(state) == "handle_error"


def test_edit_mode_never_repairs():
    state = {"exec_error": "traceback", "attempt_count": 0, "mode": "edit"}
    assert after_execute(state) == "handle_error"
