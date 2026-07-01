"""POST /datasets — upload a CSV, profile its schema, bind it to a session."""
from __future__ import annotations

import json
import re
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy.orm import Session as OrmSession

from analysis.loader import file_type_for, load_file, profile_dataframe
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


_ALLOWED_SUFFIXES = (".csv", ".xlsx", ".xls")


def _unique_df_name(session: OrmSession, session_id: str, name: str) -> str:
    """Ensure df_name is unique within a session's bound datasets.

    On collision, suffix with _2, _3, ... so the sandbox namespace has distinct
    frames (e.g. a second `sales` becomes `sales_2`).
    """
    existing: set[str] = set()
    binds = (
        session.query(SessionDataset)
        .filter(SessionDataset.session_id == session_id)
        .all()
    )
    for bind in binds:
        ds = session.get(Dataset, bind.dataset_id)
        if ds is not None:
            existing.add(ds.df_name)
    if name not in existing:
        return name
    i = 2
    while f"{name}_{i}" in existing:
        i += 1
    return f"{name}_{i}"


@router.post("/datasets")
async def upload_dataset(
    file: UploadFile = File(...),
    session_id: str | None = Form(default=None),
    df_name: str | None = Form(default=None),
    session: OrmSession = Depends(get_session),
) -> dict:
    fname = (file.filename or "").lower()
    if not fname.endswith(_ALLOWED_SUFFIXES):
        raise api_error(
            "BAD_REQUEST",
            "Only CSV and Excel (.xlsx) files are supported.",
            400,
        )

    _UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    dest = _UPLOAD_DIR / f"{uuid.uuid4().hex}_{Path(file.filename).name}"

    try:
        content = await file.read()
        dest.write_bytes(content)
    except Exception as exc:  # noqa: BLE001
        raise api_error("INTERNAL_ERROR", f"Failed to store file: {exc}", 500)

    file_type = file_type_for(file.filename or dest.name)

    try:
        df = load_file(str(dest), file_type)
    except Exception as exc:  # noqa: BLE001
        dest.unlink(missing_ok=True)
        kind = "Excel" if file_type == "xlsx" else "CSV"
        raise api_error("BAD_REQUEST", f"Could not parse {kind}: {exc}", 400)

    if df.empty or len(df.columns) == 0:
        dest.unlink(missing_ok=True)
        raise api_error("BAD_REQUEST", "The uploaded table is empty.", 400)

    profile = profile_dataframe(df)

    # Create session if none provided.
    if session_id:
        sess = session.get(Session, session_id)
        if sess is None:
            dest.unlink(missing_ok=True)
            raise api_error("NOT_FOUND", f"Session {session_id} not found.", 404)
    else:
        sess = Session(title=Path(file.filename).name if file.filename else None)
        session.add(sess)
        session.flush()
        session_id = sess.id

    requested_name = (df_name or "").strip() or _derive_df_name(file.filename)
    resolved_name = _unique_df_name(session, session_id, requested_name)

    dataset = Dataset(
        df_name=resolved_name,
        filename=Path(file.filename).name,
        file_path=str(dest),
        file_type=file_type,
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
