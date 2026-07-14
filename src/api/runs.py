import json

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from api._common import api_error, ok
from config.settings import ALLOWED_MODEL_IDS
from db.models import RunRow
from db.session import get_session
from domain.run import RunRequest
from graph.runner import run_agent

router = APIRouter()


@router.post("/runs")
def create_run(req: RunRequest) -> dict:
    if not req.prompt or not req.prompt.strip():
        raise api_error("INVALID_PROMPT", "prompt must be a non-empty string", 400)
    if req.model_id not in ALLOWED_MODEL_IDS:
        raise api_error(
            "INVALID_MODEL",
            f"model_id must be one of {sorted(ALLOWED_MODEL_IDS)}",
            400,
        )

    try:
        result = run_agent(req.prompt, req.model_id, mode="generate")
    except Exception as exc:  # noqa: BLE001 — unexpected internal error
        raise api_error("INTERNAL", f"unexpected error: {exc}", 500)

    # A Gemini transport/auth failure surfaces as HTTP 502.
    if result.get("status") == "failed" and result.get("llm_error"):
        raise api_error(
            "LLM_UNREACHABLE",
            result.get("error") or "Gemini API unreachable",
            502,
        )

    # Pipeline failures (safety violation / repairs exhausted / export error)
    # are user-visible: HTTP 200 with data.status == "failed".
    return ok(result)


@router.get("/runs/{run_id}")
def get_run(run_id: str, session: Session = Depends(get_session)) -> dict:
    run = session.get(RunRow, run_id)
    if run is None:
        raise api_error("NOT_FOUND", f"Run {run_id} not found", 404)
    if run.output_text:
        try:
            return ok(json.loads(run.output_text))
        except json.JSONDecodeError:
            pass
    # No persisted result JSON (e.g. a pending row) — return a minimal envelope.
    return ok(
        {
            "run_id": run.id,
            "status": run.status,
            "error": run.error_message,
        }
    )
