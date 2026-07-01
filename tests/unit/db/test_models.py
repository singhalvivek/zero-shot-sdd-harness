"""DB model tests — no LLM key required.

Verifies the data-analysis schema (Dataset, Session, SessionDataset, Message,
AuditLog) imports, has correct tablenames, and round-trips through a session.
"""
import json

from sqlalchemy.orm import Session as OrmSession

from db.models import (
    AuditLog,
    Base,
    Dataset,
    Message,
    Session,
    SessionDataset,
)


def test_models_import_and_tablenames():
    assert Dataset.__tablename__ == "dataset"
    assert Session.__tablename__ == "session"
    assert SessionDataset.__tablename__ == "session_dataset"
    assert Message.__tablename__ == "message"
    assert AuditLog.__tablename__ == "audit_log"


def test_runrow_is_gone():
    """The superseded skeleton table must not exist anymore."""
    assert "runs" not in Base.metadata.tables
    assert not hasattr(__import__("db.models", fromlist=["x"]), "RunRow")


def test_dataset_roundtrip(_isolated_db):
    schema = {"row_count": 2, "columns": [{"name": "dept", "dtype": "object"}]}
    with OrmSession(_isolated_db) as s:
        ds = Dataset(
            df_name="sales",
            filename="sales.csv",
            file_path="data/uploads/sales.csv",
            file_type="csv",
            row_count=2,
            schema_json=json.dumps(schema),
        )
        s.add(ds)
        s.commit()
        ds_id = ds.id

    with OrmSession(_isolated_db) as s:
        fetched = s.get(Dataset, ds_id)
        assert fetched is not None
        assert fetched.df_name == "sales"
        assert fetched.file_type == "csv"
        assert fetched.row_count == 2
        assert json.loads(fetched.schema_json)["columns"][0]["name"] == "dept"
        assert fetched.created_at is not None


def test_session_and_audit_roundtrip(_isolated_db):
    with OrmSession(_isolated_db) as s:
        sess = Session(title="My analysis")
        s.add(sess)
        s.commit()
        sess_id = sess.id

        log = AuditLog(
            session_id=sess_id,
            question="What is the average salary by department?",
            answer="Engineering pays the most at 95000.",
            prompt_tokens=120,
            completion_tokens=40,
            status="completed",
        )
        msg = Message(session_id=sess_id, role="user", content="hello")
        s.add_all([log, msg])
        s.commit()
        log_id = log.id

    with OrmSession(_isolated_db) as s:
        fetched_sess = s.get(Session, sess_id)
        assert fetched_sess.title == "My analysis"
        assert fetched_sess.created_at is not None
        assert fetched_sess.updated_at is not None

        fetched_log = s.get(AuditLog, log_id)
        assert fetched_log.session_id == sess_id
        assert fetched_log.status == "completed"
        assert fetched_log.prompt_tokens == 120
        assert fetched_log.error_message is None


def test_audit_log_nullable_fields(_isolated_db):
    """A failed query: answer/tokens null, error set, status=failed."""
    with OrmSession(_isolated_db) as s:
        sess = Session()
        s.add(sess)
        s.commit()
        log = AuditLog(
            session_id=sess.id,
            question="broken question",
            status="failed",
            error_message="boom",
        )
        s.add(log)
        s.commit()
        log_id = log.id

    with OrmSession(_isolated_db) as s:
        fetched = s.get(AuditLog, log_id)
        assert fetched.answer is None
        assert fetched.prompt_tokens is None
        assert fetched.completion_tokens is None
        assert fetched.error_message == "boom"


def test_session_dataset_composite_pk(_isolated_db):
    with OrmSession(_isolated_db) as s:
        sess = Session()
        ds = Dataset(
            df_name="t",
            filename="t.csv",
            file_path="p",
            file_type="csv",
            row_count=0,
            schema_json="{}",
        )
        s.add_all([sess, ds])
        s.commit()
        link = SessionDataset(session_id=sess.id, dataset_id=ds.id)
        s.add(link)
        s.commit()

        rows = s.query(SessionDataset).all()
        assert len(rows) == 1
        assert rows[0].session_id == sess.id
        assert rows[0].dataset_id == ds.id
