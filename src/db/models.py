from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import Text, TIMESTAMP, Integer, Float, ForeignKey
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def _uuid() -> str:
    return str(uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class RunRow(Base):
    """One row per pipeline invocation (generate / modify / edit)."""

    __tablename__ = "runs"

    id: Mapped[str] = mapped_column(Text, primary_key=True, default=_uuid)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="pending")
    input_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    output_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, default=_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, default=_now, onupdate=_now
    )


class PartRow(Base):
    """A part = one modification chain, born from a generate_part run."""

    __tablename__ = "parts"

    id: Mapped[str] = mapped_column(Text, primary_key=True, default=_uuid)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    latest_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, default=_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, default=_now, onupdate=_now
    )


class VersionRow(Base):
    """One row per successfully-persisted version (generate=v1, modify/edit=+1)."""

    __tablename__ = "versions"

    id: Mapped[str] = mapped_column(Text, primary_key=True, default=_uuid)
    part_id: Mapped[str] = mapped_column(
        Text, ForeignKey("parts.id"), nullable=False
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    # Null for v1; set for modify/edit — the modification chain (self-FK).
    parent_version_id: Mapped[str | None] = mapped_column(
        Text, ForeignKey("versions.id"), nullable=True
    )
    source: Mapped[str] = mapped_column(Text, nullable=False)  # generate | modify | edit
    prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    model_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    code_path: Mapped[str] = mapped_column(Text, nullable=False)
    stl_path: Mapped[str] = mapped_column(Text, nullable=False)
    step_path: Mapped[str] = mapped_column(Text, nullable=False)
    # Phase 2; null until the client uploads a captured thumbnail.
    thumbnail_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    repair_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    token_usage: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON
    cost_usd: Mapped[float | None] = mapped_column(Float, nullable=True)
    run_id: Mapped[str] = mapped_column(
        Text, ForeignKey("runs.id"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, default=_now
    )
