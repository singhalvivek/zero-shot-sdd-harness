from config.settings import get_settings
from graph.state import AgentState


def entry_route(state: AgentState) -> str:
    """Edit mode skips generation; everything else generates first."""
    return "static_safety_check" if state.get("mode") == "edit" else "generate_code"


def after_generate(state: AgentState) -> str:
    return "handle_error" if state.get("error") else "static_safety_check"


def after_safety(state: AgentState) -> str:
    return "handle_error" if state.get("error") else "execute_cadquery"


def after_execute(state: AgentState) -> str:
    """The repair-loop bound lives HERE (not inside a node)."""
    if not state.get("exec_error"):
        return "export_model"
    max_attempts = get_settings().max_repair_attempts
    if state.get("attempt_count", 0) < max_attempts and state.get("mode") != "edit":
        return "repair_on_error"
    return "handle_error"
