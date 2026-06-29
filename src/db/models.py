from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import ForeignKey, Integer, Text, TIMESTAMP
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def _uuid() -> str:
    return str(uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class Dataset(Base):
    """An uploaded tabular file and its profiled schema (columns + dtypes only)."""

    __tablename__ = "dataset"

    id: Mapped[str] = mapped_column(Text, primary_key=True, default=_uuid)
    df_name: Mapped[str] = mapped_column(Text, nullable=False)
    filename: Mapped[str] = mapped_column(Text, nullable=False)
    file_path: Mapped[str] = mapped_column(Text, nullable=False)
    file_type: Mapped[str] = mapped_column(Text, nullable=False)
    row_count: Mapped[int] = mapped_column(Integer, nullable=False)
    # JSON document held as Text: {"columns": [{"name", "dtype"}], "row_count": int}
    schema_json: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, default=_now
    )


class Session(Base):
    """A conversation session binding datasets and holding message history."""

    __tablename__ = "session"

    id: Mapped[str] = mapped_column(Text, primary_key=True, default=_uuid)
    title: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, default=_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, default=_now, onupdate=_now
    )


class SessionDataset(Base):
    """Join table: which datasets are loaded into a session."""

    __tablename__ = "session_dataset"

    session_id: Mapped[str] = mapped_column(
        Text, ForeignKey("session.id"), primary_key=True
    )
    dataset_id: Mapped[str] = mapped_column(
        Text, ForeignKey("dataset.id"), primary_key=True
    )


class Message(Base):
    """One conversation turn (rehydrated into state.messages)."""

    __tablename__ = "message"

    id: Mapped[str] = mapped_column(Text, primary_key=True, default=_uuid)
    session_id: Mapped[str] = mapped_column(
        Text, ForeignKey("session.id"), nullable=False
    )
    role: Mapped[str] = mapped_column(Text, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, default=_now
    )


class AuditLog(Base):
    """Persisted record of every query and answer (id also serves as run_id)."""

    __tablename__ = "audit_log"

    id: Mapped[str] = mapped_column(Text, primary_key=True, default=_uuid)
    session_id: Mapped[str] = mapped_column(
        Text, ForeignKey("session.id"), nullable=False
    )
    question: Mapped[str] = mapped_column(Text, nullable=False)
    answer: Mapped[str | None] = mapped_column(Text, nullable=True)
    prompt_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    completion_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, default=_now
    )
