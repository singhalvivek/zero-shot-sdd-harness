import json
from uuid import uuid4

from db.models import PartRow, RunRow, VersionRow
from db.session import create_db_session, init_db
from graph.agent import agentic_ai
from graph.state import AgentState
from observability.events import get_logger

_log = get_logger("runner")


def _empty_usage() -> dict:
    return {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}


def _build_result(
    state: dict, run_id: str, part_id: str, version_number: int
) -> dict:
    status = state.get("status", "failed")
    completed = status == "completed"
    stl_url = (
        f"/artifacts/exports/part_{part_id}/part_v{version_number}.stl"
        if completed and state.get("stl_path")
        else None
    )
    step_url = (
        f"/artifacts/exports/part_{part_id}/part_v{version_number}.step"
        if completed and state.get("step_path")
        else None
    )
    code_url = state.get("code_path") if completed else None
    return {
        "run_id": run_id,
        "part_id": part_id,
        "version_number": version_number,
        "status": status,
        "generated_code": state.get("generated_code"),
        "repair_attempts": state.get("repair_attempts", []),
        "safety_violation": state.get("safety_violation"),
        "token_usage": state.get("token_usage", _empty_usage()),
        "cost_usd": state.get("cost_usd", 0.0),
        "stl_url": stl_url,
        "step_url": step_url,
        "code_url": code_url,
        "error": state.get("error") or state.get("exec_error"),
        "llm_error": bool(state.get("llm_error")),
    }


def run_agent(
    prompt: str,
    model_id: str,
    mode: str = "generate",
    previous_code: str | None = None,
    part_id: str | None = None,
    version_number: int | None = None,
) -> dict:
    """Run the generate_part pipeline; persist parts/versions on success.

    Returns a result dict shaped exactly like the POST /runs `data` body.
    """
    init_db()

    input_text = prompt if mode != "edit" else "<edited code>"
    with create_db_session() as session:
        run = RunRow(input_text=input_text, status="pending")
        session.add(run)
        session.flush()
        run_id = run.id

    if part_id is None:
        part_id = str(uuid4())
    if version_number is None:
        version_number = 1

    initial: AgentState = {
        "run_id": run_id,
        "part_id": part_id,
        "version_number": version_number,
        "prompt": prompt or "",
        "previous_code": previous_code,
        "model_id": model_id,
        "mode": mode,
        "generated_code": previous_code if mode == "edit" else None,
        "attempt_count": 0,
        "repair_attempts": [],
        "safety_violation": None,
        "exec_error": None,
        "token_usage": _empty_usage(),
        "cost_usd": 0.0,
        "error": None,
        "llm_error": False,
    }

    final = agentic_ai.invoke(initial)
    status = final.get("status", "failed")
    result = _build_result(final, run_id, part_id, version_number)

    with create_db_session() as session:
        run = session.get(RunRow, run_id)
        run.status = status
        run.output_text = json.dumps(result)
        run.error_message = (
            final.get("error") or final.get("exec_error") or final.get("safety_violation")
        )

        if status == "completed" and mode == "generate":
            title = (prompt or "").strip()[:60] or "Untitled part"
            session.add(
                PartRow(
                    id=part_id, title=title, latest_version=version_number
                )
            )
            session.add(
                VersionRow(
                    part_id=part_id,
                    version_number=version_number,
                    parent_version_id=None,
                    source="generate",
                    prompt=prompt,
                    model_id=model_id,
                    code_path=(result["code_url"] or "").lstrip("/"),
                    stl_path=(result["stl_url"] or "").lstrip("/"),
                    step_path=(result["step_url"] or "").lstrip("/"),
                    thumbnail_path=None,
                    repair_count=len(final.get("repair_attempts", [])),
                    token_usage=json.dumps(final.get("token_usage", _empty_usage())),
                    cost_usd=final.get("cost_usd", 0.0),
                    run_id=run_id,
                )
            )

    _log.info(
        "run_complete",
        run_id=run_id,
        part_id=part_id,
        model_id=model_id,
        mode=mode,
        status=status,
        total_tokens=result["token_usage"].get("total_tokens"),
        cost_usd=result["cost_usd"],
        repair_count=len(final.get("repair_attempts", [])),
    )
    return result
