from pathlib import Path

from config.settings import estimate_cost, get_settings
from graph.state import AgentState
from observability.events import get_logger

_PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "generate.md"
_log = get_logger("graph")


def _load_generate_prompt() -> str:
    return _PROMPT_PATH.read_text(encoding="utf-8").strip()


def _make_provider(model_id: str):
    from llm.providers.gemini import GeminiProvider

    return GeminiProvider(api_key=get_settings().gemini_api_key, model=model_id)


def _short(text: str | None, limit: int = 300) -> str:
    if not text:
        return ""
    text = text.strip().replace("\n", " ")
    return text if len(text) <= limit else text[:limit] + "…"


def _merge_usage(prev: dict, new: dict) -> dict:
    keys = ("prompt_tokens", "completion_tokens", "total_tokens")
    return {k: int(prev.get(k, 0)) + int(new.get(k, 0)) for k in keys}


def generate_code(state: AgentState) -> AgentState:
    """LLM node — Gemini writes the CadQuery code (fences stripped)."""
    model_id = state["model_id"]
    try:
        provider = _make_provider(model_id)
        system = _load_generate_prompt()
        if state.get("mode") == "modify" and state.get("previous_code"):
            user = (
                "Modify the following CadQuery part as requested.\n\n"
                f"Existing code:\n{state['previous_code']}\n\n"
                f"Requested change:\n{state['prompt']}"
            )
        else:
            user = state["prompt"]

        out = provider.generate(user, system=system)
        usage = _merge_usage(state.get("token_usage", {}), out["usage"])
        cost = round(
            state.get("cost_usd", 0.0) + estimate_cost(out["usage"], model_id), 6
        )
        _log.info(
            "generate_code",
            run_id=state.get("run_id"),
            model_id=model_id,
            prompt_tokens=out["usage"].get("prompt_tokens"),
            completion_tokens=out["usage"].get("completion_tokens"),
            code_len=len(out["text"] or ""),
        )
        return {
            **state,
            "generated_code": out["text"],
            "token_usage": usage,
            "cost_usd": cost,
        }
    except Exception as exc:  # noqa: BLE001 — Gemini transport/auth is fatal (502)
        _log.error("generate_code_error", run_id=state.get("run_id"), error=str(exc))
        return {**state, "error": f"gemini_error: {exc}", "llm_error": True}


def static_safety_check(state: AgentState) -> AgentState:
    """Reject forbidden calls before execution (runs on every attempt)."""
    from sandbox import static_safety_check as check

    violation = check(state.get("generated_code") or "")
    _log.info(
        "static_safety_check",
        run_id=state.get("run_id"),
        violation=violation,
    )
    if violation:
        return {
            **state,
            "safety_violation": violation,
            "error": f"safety_violation: {violation}",
        }
    return {**state, "safety_violation": None}


def execute_cadquery(state: AgentState) -> AgentState:
    """Execute the code in a sandboxed child process; export STL+STEP there."""
    from sandbox import run_and_export

    settings = get_settings()
    try:
        res = run_and_export(
            state["generated_code"],
            state["part_id"],
            state["version_number"],
            formats=("stl", "step"),
            timeout=settings.exec_timeout_seconds,
        )
    except Exception as exc:  # noqa: BLE001 — treated as an exec error → repair
        _log.error("execute_cadquery_crash", run_id=state.get("run_id"), error=str(exc))
        return {**state, "exec_error": f"sandbox invocation error: {exc}"}

    if res.get("ok"):
        _log.info(
            "execute_cadquery",
            run_id=state.get("run_id"),
            ok=True,
            stl_path=res.get("stl_path"),
        )
        return {
            **state,
            "stl_path": res["stl_path"],
            "step_path": res["step_path"],
            "exec_error": None,
        }

    _log.info(
        "execute_cadquery",
        run_id=state.get("run_id"),
        ok=False,
        error=_short(res.get("error")),
    )
    return {**state, "exec_error": res.get("error") or "unknown execution error"}


def repair_on_error(state: AgentState) -> AgentState:
    """LLM node — give Gemini the failing code + traceback, get corrected code."""
    model_id = state["model_id"]
    attempt = state.get("attempt_count", 0) + 1
    failing_error = state.get("exec_error")
    try:
        provider = _make_provider(model_id)
        system = _load_generate_prompt()
        user = (
            "The following CadQuery code failed when executed. Return corrected, "
            "complete CadQuery code only (no prose, no fences).\n\n"
            f"Code:\n{state.get('generated_code')}\n\n"
            f"Error:\n{failing_error}"
        )
        out = provider.generate(user, system=system)
        usage = _merge_usage(state.get("token_usage", {}), out["usage"])
        cost = round(
            state.get("cost_usd", 0.0) + estimate_cost(out["usage"], model_id), 6
        )
        repairs = list(state.get("repair_attempts", []))
        repairs.append(
            {
                "attempt": attempt,
                "error": _short(failing_error),
                "change_summary": "regenerated corrected CadQuery code",
            }
        )
        _log.info(
            "repair_on_error",
            run_id=state.get("run_id"),
            attempt=attempt,
            error=_short(failing_error),
        )
        return {
            **state,
            "generated_code": out["text"],
            "attempt_count": attempt,
            "repair_attempts": repairs,
            "token_usage": usage,
            "cost_usd": cost,
            "exec_error": None,
        }
    except Exception as exc:  # noqa: BLE001 — Gemini failure during repair is fatal
        _log.error("repair_on_error_error", run_id=state.get("run_id"), error=str(exc))
        return {**state, "error": f"gemini_error: {exc}", "llm_error": True}


def export_model(state: AgentState) -> AgentState:
    """Persist the versioned source; STL/STEP were written inside execute."""
    from sandbox import write_code_artifacts

    try:
        code_url = write_code_artifacts(
            state["part_id"], state["version_number"], state.get("generated_code") or ""
        )
        return {**state, "code_path": code_url}
    except Exception as exc:  # noqa: BLE001 — a write failure fails the run
        _log.error("export_model_error", run_id=state.get("run_id"), error=str(exc))
        return {**state, "error": f"export_error: {exc}"}


def finalize(state: AgentState) -> AgentState:
    status = "failed" if state.get("error") else "completed"
    return {**state, "status": status}


def handle_error(state: AgentState) -> AgentState:
    return {**state, "status": "failed"}
