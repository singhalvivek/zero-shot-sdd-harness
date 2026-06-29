"""Session endpoints: GET /sessions/{id} and POST /sessions/{id}/ask (SSE)."""
from __future__ import annotations

import json

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session as OrmSession

from api._common import api_error, ok
from db.models import Dataset, Message, Session, SessionDataset
from db.session import get_session
from graph.runner import NoDatasetBound, SessionNotFound, stream_ask

router = APIRouter()


class AskRequest(BaseModel):
    question: str


@router.get("/sessions/{session_id}")
def get_session_detail(
    session_id: str, session: OrmSession = Depends(get_session)
) -> dict:
    sess = session.get(Session, session_id)
    if sess is None:
        raise api_error("NOT_FOUND", f"Session {session_id} not found.", 404)

    binds = (
        session.query(SessionDataset)
        .filter(SessionDataset.session_id == session_id)
        .all()
    )
    datasets = []
    for bind in binds:
        ds = session.get(Dataset, bind.dataset_id)
        if ds is None:
            continue
        datasets.append(
            {
                "dataset_id": ds.id,
                "df_name": ds.df_name,
                "filename": ds.filename,
                "row_count": ds.row_count,
                "columns": json.loads(ds.schema_json).get("columns", []),
            }
        )

    messages = [
        {"role": m.role, "content": m.content}
        for m in session.query(Message)
        .filter(Message.session_id == session_id)
        .order_by(Message.created_at.asc())
        .all()
    ]

    return ok({"session_id": session_id, "datasets": datasets, "messages": messages})


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


@router.post("/sessions/{session_id}/ask")
async def ask(session_id: str, req: AskRequest):
    # Validate up front so we can return a proper HTTP status before streaming.
    if not req.question or not req.question.strip():
        raise api_error("BAD_REQUEST", "question must not be empty.", 400)

    try:
        agen = stream_ask(session_id, req.question)
        first = await agen.__anext__()  # triggers _prepare validation
    except SessionNotFound:
        raise api_error("NOT_FOUND", f"Session {session_id} not found.", 404)
    except NoDatasetBound:
        raise api_error("BAD_REQUEST", "No dataset is bound to this session.", 400)
    except ValueError as exc:
        raise api_error("BAD_REQUEST", str(exc), 400)

    async def event_stream():
        yield _sse(first["event"], first["data"])
        async for ev in agen:
            yield _sse(ev["event"], ev["data"])

    return StreamingResponse(event_stream(), media_type="text/event-stream")
