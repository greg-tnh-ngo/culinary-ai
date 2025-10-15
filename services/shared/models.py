# services/shared/models.py
from __future__ import annotations
from datetime import datetime
from typing import Any
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import Integer, String, DateTime
from sqlalchemy.dialects.postgresql import JSONB

class Base(DeclarativeBase):
    pass

class PipelineRun(Base):
    __tablename__ = "pipeline_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    kind: Mapped[str] = mapped_column(String(32))  # "SHORT" or "LONG"
    idea: Mapped[dict[str, Any]] = mapped_column(JSONB)
    scripts: Mapped[dict[str, Any]] = mapped_column(JSONB)  # store as {"items": [...]}
    shoot_card: Mapped[dict[str, Any]] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
