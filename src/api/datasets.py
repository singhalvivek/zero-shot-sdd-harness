"""POST /datasets — upload a CSV, profile its schema, bind it to a session."""
from __future__ import annotations

import json
import re
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy.orm import Session as OrmSession

from analysis.loader import load_csv, profile_dataframe
from api._common import api_error, ok
from db.models import Dataset, Session, SessionDataset
from db.session import get_session

router = APIRouter()

_UPLOAD_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "uploads"


def _derive_df_name(filename: str) -> str:
    stem = Path(filename or "data").stem
    cleaned = re.sub(r"[^0-9a-zA-Z_]", "_", stem).strip("_").lower()
    if not cleaned or cleaned[0].isdigit():
        cleaned = f"df_{cleaned}" if cleaned else "df"
    return cleaned


@router.post("/datasets")
async def upload_dataset(
    file: UploadFile = File(...),
    session_id: str | None = Form(default=None),
    df_name: str | None = Form(default=None),
    session: OrmSession = Depends(get_session),
) -> dict:
    if not (file.filename or "").lower().endswith(".csv"):
        raise api_error("BAD_REQUEST", "Only CSV files are supported in Phase 1.", 400)

    _UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    dest = _UPLOAD_DIR / f"{uuid.uuid4().hex}_{Path(file.filename).name}"

    try:
        content = await file.read()
        dest.write_bytes(content)
    except Exception as exc:  # noqa: BLE001
        raise api_error("INTERNAL_ERROR", f"Failed to store file: {exc}", 500)

    try:
        df = load_csv(str(dest))
    except Exception as exc:  # noqa: BLE001
        dest.unlink(missing_ok=True)
        raise api_error("BAD_REQUEST", f"Could not parse CSV: {exc}", 400)

    if df.empty or len(df.columns) == 0:
        dest.unlink(missing_ok=True)
        raise api_error("BAD_REQUEST", "The uploaded table is empty.", 400)

    profile = profile_dataframe(df)
    resolved_name = (df_name or "").strip() or _derive_df_name(file.filename)

    # Create session if none provided.
    if session_id:
        sess = session.get(Session, session_id)
        if sess is None:
            dest.unlink(missing_ok=True)
            raise api_error("NOT_FOUND", f"Session {session_id} not found.", 404)
    else:
        sess = Session()
        session.add(sess)
        session.flush()
        session_id = sess.id

    dataset = Dataset(
        df_name=resolved_name,
        filename=Path(file.filename).name,
        file_path=str(dest),
        file_type="csv",
        row_count=profile["row_count"],
        schema_json=json.dumps(profile),
    )
    session.add(dataset)
    session.flush()
    session.add(SessionDataset(session_id=session_id, dataset_id=dataset.id))

    return ok(
        {
            "dataset_id": dataset.id,
            "df_name": resolved_name,
            "row_count": profile["row_count"],
            "columns": profile["columns"],
            "session_id": session_id,
        }
    )
