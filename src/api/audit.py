"""Audit-log viewer endpoint: GET /audit (optionally filtered by session_id)."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session as OrmSession

from api._common import ok
from db.models import AuditLog
from db.session import get_session

router = APIRouter()


@router.get("/audit")
def list_audit(
    session_id: str | None = None,
    session: OrmSession = Depends(get_session),
) -> dict:
    query = session.query(AuditLog)
    if session_id:
        query = query.filter(AuditLog.session_id == session_id)
    rows = query.order_by(AuditLog.created_at.desc()).all()
    return ok(
        [
            {
                "id": r.id,
                "session_id": r.session_id,
                "question": r.question,
                "answer": r.answer,
                "prompt_tokens": r.prompt_tokens,
                "completion_tokens": r.completion_tokens,
                "status": r.status,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ]
    )
