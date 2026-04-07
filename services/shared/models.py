# services/shared/models.py
from __future__ import annotations
import uuid
from datetime import datetime, date
from decimal import Decimal
from enum import Enum
from typing import Any, Optional
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy import Integer, String, DateTime, Text, SmallInteger, Numeric, Date, ForeignKey, Boolean
from sqlalchemy import TIMESTAMP
from sqlalchemy.dialects.postgresql import JSONB, UUID


class Base(DeclarativeBase):
    pass


class StreamType(str, Enum):
    SHORT = "SHORT"
    LONG = "LONG"
    SHORT_LONG = "SHORT+LONG"


class VideoStatus(str, Enum):
    IDEA = "IDEA"
    SCRIPT = "SCRIPT"
    SHOT = "SHOT"
    EDIT = "EDIT"
    QC = "QC"
    READY = "READY"
    SCHEDULED = "SCHEDULED"
    PUBLISHED = "PUBLISHED"


class ScriptVariant(str, Enum):
    TUTORIAL = "TUTORIAL"
    PERSONAL = "PERSONAL"


class PipelineRun(Base):
    __tablename__ = "pipeline_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    kind: Mapped[str] = mapped_column(String(32))  # "SHORT" or "LONG"
    idea: Mapped[dict[str, Any]] = mapped_column(JSONB)
    scripts: Mapped[dict[str, Any]] = mapped_column(JSONB)  # store as {"items": [...]}
    shoot_card: Mapped[dict[str, Any]] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class Video(Base):
    __tablename__ = "videos"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid.uuid4()))
    title: Mapped[str] = mapped_column(Text, nullable=False)
    stream: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, default=VideoStatus.IDEA)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default="now()", nullable=False)
    approved_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    release_packet: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    feedback: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    scripts: Mapped[list[Script]] = relationship("Script", back_populates="video")


class Script(Base):
    __tablename__ = "scripts"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid.uuid4()))
    video_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("videos.id"), nullable=False)
    variant: Mapped[str] = mapped_column(Text, nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    verification: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    chapters: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default="now()", nullable=False)

    video: Mapped[Video] = relationship("Video", back_populates="scripts")


class Source(Base):
    __tablename__ = "sources"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid.uuid4()))
    script_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("scripts.id"), nullable=False)
    url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    quoted: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    accessed_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)


class Ingredient(Base):
    __tablename__ = "ingredients"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    category: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    unit: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    avg_price_per_unit: Mapped[Optional[Decimal]] = mapped_column(Numeric, nullable=True)
    current_qty: Mapped[Decimal] = mapped_column(Numeric, server_default="0", nullable=False)
    expiry_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)


class Recipe(Base):
    __tablename__ = "recipes"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid.uuid4()))
    title: Mapped[str] = mapped_column(Text, nullable=False)
    difficulty: Mapped[Optional[int]] = mapped_column(SmallInteger, nullable=True)
    time_required_minutes: Mapped[Optional[int]] = mapped_column(SmallInteger, nullable=True)
    stream: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class RecipeIngredient(Base):
    __tablename__ = "recipe_ingredients"

    recipe_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("recipes.id"), primary_key=True)
    ingredient_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("ingredients.id"), primary_key=True)
    qty: Mapped[Optional[Decimal]] = mapped_column(Numeric, nullable=True)


class LedgerWeek(Base):
    __tablename__ = "ledger_weeks"

    week_id: Mapped[date] = mapped_column(Date, primary_key=True)
    budget_limit: Mapped[Decimal] = mapped_column(Numeric, server_default="100", nullable=False)
    planned_spend: Mapped[Decimal] = mapped_column(Numeric, server_default="0", nullable=False)
    actual_spend: Mapped[Decimal] = mapped_column(Numeric, server_default="0", nullable=False)
    planned_recipe_ids: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB, nullable=True)


class Purchase(Base):
    __tablename__ = "purchases"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid.uuid4()))
    occurred_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    store: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    items: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    total: Mapped[Optional[Decimal]] = mapped_column(Numeric, nullable=True)


class VideoMetric(Base):
    __tablename__ = "video_metrics"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid.uuid4()))
    video_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("videos.id"), nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default="now()", nullable=False)
    platform: Mapped[str] = mapped_column(Text, nullable=False)
    views: Mapped[int] = mapped_column(Integer, server_default="0", nullable=False)
    watch_time_seconds: Mapped[int] = mapped_column(Integer, server_default="0", nullable=False)
    retention_pct: Mapped[Decimal] = mapped_column(Numeric, server_default="0", nullable=False)
    likes: Mapped[int] = mapped_column(Integer, server_default="0", nullable=False)
    comments: Mapped[int] = mapped_column(Integer, server_default="0", nullable=False)
    shares: Mapped[int] = mapped_column(Integer, server_default="0", nullable=False)


class LlmCall(Base):
    __tablename__ = "llm_calls"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    agent: Mapped[str] = mapped_column(Text, nullable=False)
    model: Mapped[str] = mapped_column(Text, nullable=False)
    input_tokens: Mapped[int] = mapped_column(Integer, nullable=False)
    output_tokens: Mapped[int] = mapped_column(Integer, nullable=False)
    cost_usd: Mapped[Decimal] = mapped_column(Numeric(12, 8), nullable=False)
    duration_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    succeeded: Mapped[bool] = mapped_column(Boolean, nullable=False)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default="now()", nullable=False)


class RequestLog(Base):
    __tablename__ = "request_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    endpoint: Mapped[str] = mapped_column(Text, nullable=False)
    method: Mapped[str] = mapped_column(Text, nullable=False)
    status_code: Mapped[int] = mapped_column(Integer, nullable=False)
    duration_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), server_default="now()", nullable=False)
