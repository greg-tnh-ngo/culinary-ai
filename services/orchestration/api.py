# services/orchestration/api.py
from fastapi import FastAPI, HTTPException
from fastapi.responses import PlainTextResponse, HTMLResponse
import asyncio
import time as _time
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request as StarletteRequest
import pathlib
import uuid as _uuid
import re as _re
import os
from contextlib import asynccontextmanager
import logging as _api_log
from services.agents.julien.main import curate_stub
from services.agents.marcel.main import write_scripts
from services.agents.camille.main import make_shoot_card
from services.agents.pierre.main import make_edit_directive
from services.agents.colette.main import make_release_packet
from services.agents.lucien.main import adapt_for_platforms
from services.agents.armand.main import plan_week, ingest_receipt, get_grocery_list
from services.agents.etienne.main import generate_weekly_report
from pydantic import BaseModel, field_validator
from typing import List, Optional
from datetime import date, timedelta
from fastapi import UploadFile, File

_log = _api_log.getLogger(__name__)
_DATE_RE = _re.compile(r"^\d{4}-\d{2}-\d{2}$")

from services.shared.db import ping_db, engine
from services.shared.repo import (
    save_pipeline_run,
    get_pipeline_run,
    create_video,
    update_video_status,
    save_script,
    save_release_packet,
    approve_video,
    request_changes,
    save_video_metric,
    get_video_metrics,
    get_video,
    list_videos,
    list_ingredients,
    create_ingredient,
    list_recipes,
    create_recipe,
    add_recipe_ingredient,
    get_recipe_with_ingredients,
    get_or_create_ledger_week,
    get_grocery_list as repo_get_grocery_list,
    record_request_log,
    get_cost_summary,
    get_latency_summary,
    get_slo_status,
)


class ChangesRequest(BaseModel):
    feedback: str


class RecipeCreate(BaseModel):
    title: str
    difficulty: Optional[int] = None
    time_required_minutes: Optional[int] = None
    stream: Optional[str] = None
    ingredients: List[dict] = []  # [{"ingredient_id": str, "qty": float}]


class WeekPlanRequest(BaseModel):
    recipe_ids: List[str]
    week_id: Optional[str] = None  # ISO date YYYY-MM-DD; defaults to current Monday


class MetricsIngest(BaseModel):
    platform: str
    views: int = 0
    watch_time_seconds: int = 0
    retention_pct: float = 0.0
    likes: int = 0
    comments: int = 0
    shares: int = 0

    @field_validator("retention_pct")
    @classmethod
    def _check_retention(cls, v: float) -> float:
        if not (0.0 <= v <= 100.0):
            raise ValueError("retention_pct must be between 0 and 100")
        return v


class IngredientCreate(BaseModel):
    name: str
    category: Optional[str] = None
    unit: Optional[str] = None
    avg_price_per_unit: Optional[float] = None

    @field_validator("avg_price_per_unit")
    @classmethod
    def _check_price(cls, v):
        if v is not None and v < 0:
            raise ValueError("avg_price_per_unit must not be negative")
        return v


def _validate_uuid(value: str, field: str = "id") -> str:
    """Raise HTTPException(422) if value is not a valid UUID. Returns value unchanged."""
    try:
        _uuid.UUID(value)
    except ValueError:
        raise HTTPException(status_code=422, detail=f"{field} must be a valid UUID")
    return value


def _validate_date(value: str, field: str = "week_id") -> date:
    """Raise HTTPException(422) if value is not YYYY-MM-DD. Returns parsed date."""
    if not _DATE_RE.match(value):
        raise HTTPException(status_code=422, detail=f"{field} must be YYYY-MM-DD")
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise HTTPException(status_code=422, detail=f"{field} is not a valid date")


@asynccontextmanager
async def _lifespan(app: FastAPI):
    _log.info("culinary-ai API starting up")
    if ping_db():
        _log.info("startup: DB connection OK")
    else:
        _log.error("startup: DB connection FAILED — service may be degraded")
    yield
    _log.info("culinary-ai API shutting down gracefully")


app = FastAPI(title="Culinary AI", lifespan=_lifespan)


class _RequestTimingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: StarletteRequest, call_next):
        t0 = _time.perf_counter()
        response = await call_next(request)
        duration_ms = int((_time.perf_counter() - t0) * 1000)
        asyncio.create_task(
            _write_request_log(request.url.path, request.method, response.status_code, duration_ms)
        )
        return response


async def _write_request_log(endpoint: str, method: str, status_code: int, duration_ms: int) -> None:
    try:
        record_request_log(endpoint, method, status_code, duration_ms)
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning("request_log write failed: %s", e)


app.add_middleware(_RequestTimingMiddleware)

_DASHBOARD_HTML = pathlib.Path(__file__).parent.parent.parent / "apps" / "dashboard" / "index.html"

@app.get("/dashboard", response_class=HTMLResponse)
def dashboard():
    return _DASHBOARD_HTML.read_text()

@app.get("/health")
def health_check():
    from sqlalchemy import text as _text
    db_ok = ping_db()

    migration_version = None
    try:
        with engine.connect() as conn:
            row = conn.execute(_text("SELECT version_num FROM alembic_version LIMIT 1")).first()
            migration_version = row[0] if row else None
    except Exception:
        migration_version = None

    api_key_present = bool(os.environ.get("ANTHROPIC_API_KEY", "").strip())

    status = "ok" if db_ok else "degraded"
    return {
        "status": status,
        "db": "ok" if db_ok else "down",
        "migrations": migration_version,
        "api_key_present": api_key_present,
    }

@app.get("/ideas/draft")
def draft_idea():
    return curate_stub().model_dump()

@app.get("/pipeline/short/preview")
def pipeline_short_preview():
    idea = curate_stub().model_dump()
    scripts = [s.model_dump() for s in write_scripts(idea)]
    tutorial_body = next((s["body"] for s in scripts if s["variant"] == "TUTORIAL"), scripts[0]["body"])
    shoot = make_shoot_card(tutorial_body).model_dump()
    return {"idea": idea, "scripts": scripts, "shoot_card": shoot}

@app.post("/pipeline/short/run")
def pipeline_short_run():
    try:
        idea = curate_stub().model_dump()
        scripts = [s.model_dump() for s in write_scripts(idea)]
        tutorial_body = next((s["body"] for s in scripts if s["variant"] == "TUTORIAL"), scripts[0]["body"])
        shoot = make_shoot_card(tutorial_body).model_dump()

        video_id = create_video(title=idea.get("title", "Untitled"), stream="SHORT")
        for s in scripts:
            save_script(
                video_id=video_id,
                variant=s["variant"],
                body=s["body"],
                verification=s.get("verification"),
            )
        update_video_status(video_id, "SCRIPT")

        run_id = save_pipeline_run("SHORT", idea, scripts, shoot)
        return {"run_id": run_id, "video_id": video_id}
    except HTTPException:
        raise
    except Exception:
        _log.exception("Error in pipeline_short_run")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.get("/pipeline/long/preview")
def pipeline_long_preview():
    idea = curate_stub().model_dump()
    scripts = [s.model_dump() for s in write_scripts(idea, stream="LONG")]
    tutorial_body = next((s["body"] for s in scripts if s["variant"] == "TUTORIAL"), scripts[0]["body"])
    shoot = make_shoot_card(tutorial_body).model_dump()
    return {"idea": idea, "scripts": scripts, "shoot_card": shoot}


@app.post("/pipeline/long/run")
def pipeline_long_run():
    try:
        idea = curate_stub().model_dump()
        scripts = [s.model_dump() for s in write_scripts(idea, stream="LONG")]
        tutorial_body = next((s["body"] for s in scripts if s["variant"] == "TUTORIAL"), scripts[0]["body"])
        shoot = make_shoot_card(tutorial_body).model_dump()

        video_id = create_video(title=idea.get("title", "Untitled"), stream="LONG")
        for s in scripts:
            save_script(
                video_id=video_id,
                variant=s["variant"],
                body=s["body"],
                verification=s.get("verification"),
                chapters=s.get("chapters"),
            )
        update_video_status(video_id, "SCRIPT")

        run_id = save_pipeline_run("LONG", idea, scripts, shoot)
        return {"run_id": run_id, "video_id": video_id}
    except HTTPException:
        raise
    except Exception:
        _log.exception("Error in pipeline_long_run")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/pipeline/run/{run_id}")
def pipeline_get(run_id: int):
    row = get_pipeline_run(run_id)
    if not row:
        raise HTTPException(status_code=404, detail="run not found")
    return row

@app.get("/videos")
def videos_list():
    return list_videos()

@app.get("/videos/{video_id}")
def video_get(video_id: str):
    _validate_uuid(video_id, "video_id")
    row = get_video(video_id)
    if not row:
        raise HTTPException(status_code=404, detail="video not found")
    return row

@app.post("/pipeline/short/qc/{video_id}")
def pipeline_short_qc(video_id: str):
    try:
        _validate_uuid(video_id, "video_id")
        video = get_video(video_id)
        if not video:
            raise HTTPException(status_code=404, detail="video not found")
        scripts = video["scripts"]
        edit_directive = make_edit_directive(shoot_card={}, scripts=scripts)
        release_packet = make_release_packet(video_id, scripts, edit_directive.model_dump(), {})
        if release_packet.qc.overall_pass:
            update_video_status(video_id, "QC")
            save_release_packet(video_id, release_packet.model_dump())
        return {
            "video_id": video_id,
            "edit_directive": edit_directive.model_dump(),
            "release_packet": release_packet.model_dump(),
        }
    except HTTPException:
        raise
    except Exception:
        _log.exception("Error in pipeline_short_qc")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.post("/videos/{video_id}/approve")
def video_approve(video_id: str):
    try:
        _validate_uuid(video_id, "video_id")
        video = get_video(video_id)
        if not video:
            raise HTTPException(status_code=404, detail="video not found")
        if video["status"] != "QC":
            raise HTTPException(status_code=400, detail=f"video is in status '{video['status']}', must be QC to approve")
        release_packet = video.get("release_packet")
        if not release_packet:
            raise HTTPException(status_code=400, detail="no release packet found — run QC first")
        platform_packet = adapt_for_platforms(video_id, release_packet)
        approve_video(video_id)
        return {
            "video_id": video_id,
            "status": "SCHEDULED",
            "platform_packet": platform_packet.model_dump(),
        }
    except HTTPException:
        raise
    except Exception:
        _log.exception("Error in video_approve")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.post("/videos/{video_id}/request-changes")
def video_request_changes(video_id: str, body: ChangesRequest):
    _validate_uuid(video_id, "video_id")
    video = get_video(video_id)
    if not video:
        raise HTTPException(status_code=404, detail="video not found")
    request_changes(video_id, body.feedback)
    return {"video_id": video_id, "status": "SCRIPT", "feedback": body.feedback}


# ── Armand: ingredients ───────────────────────────────────────────────────────

@app.get("/armand/ingredients")
def armand_list_ingredients():
    return list_ingredients()


@app.post("/armand/ingredients")
def armand_create_ingredient(body: IngredientCreate):
    ingredient_id = create_ingredient(body.name, body.category, body.unit, body.avg_price_per_unit)
    return {"id": ingredient_id, "name": body.name}


# ── Armand: recipes ───────────────────────────────────────────────────────────

@app.get("/armand/recipes")
def armand_list_recipes():
    return list_recipes()


@app.post("/armand/recipes")
def armand_create_recipe(body: RecipeCreate):
    recipe_id = create_recipe(body.title, body.difficulty, body.time_required_minutes, body.stream)
    for ing in body.ingredients:
        add_recipe_ingredient(recipe_id, ing["ingredient_id"], ing.get("qty"))
    return get_recipe_with_ingredients(recipe_id)


@app.get("/armand/recipes/{recipe_id}")
def armand_get_recipe(recipe_id: str):
    _validate_uuid(recipe_id, "recipe_id")
    row = get_recipe_with_ingredients(recipe_id)
    if not row:
        raise HTTPException(status_code=404, detail="recipe not found")
    return row


# ── Armand: week planning ─────────────────────────────────────────────────────

@app.post("/armand/plan")
def armand_plan_week(body: WeekPlanRequest):
    if body.week_id:
        try:
            week_date = date.fromisoformat(body.week_id)
        except ValueError:
            raise HTTPException(status_code=422, detail="week_id must be a valid YYYY-MM-DD date")
    else:
        week_date = None
    result = plan_week(body.recipe_ids, week_date)
    return result.model_dump()


@app.get("/armand/ledger/{week_id}")
def armand_get_ledger(week_id: str):
    try:
        week_date = date.fromisoformat(week_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="week_id must be ISO date YYYY-MM-DD")
    return get_or_create_ledger_week(week_date)


# ── Armand: receipt ingestion ─────────────────────────────────────────────────

@app.post("/armand/receipt")
async def armand_ingest_receipt(store: str = "unknown", file: UploadFile = File(...)):
    image_bytes = await file.read()
    result = ingest_receipt(image_bytes, store)
    return result.model_dump()


# ── Armand: grocery list ──────────────────────────────────────────────────────

@app.get("/armand/grocery-list/{week_id}")
def armand_grocery_list(week_id: str):
    try:
        week = _validate_date(week_id, "week_id")
        result = get_grocery_list(week)
        return result.model_dump()
    except HTTPException:
        raise
    except Exception:
        _log.exception("Error in armand_grocery_list")
        raise HTTPException(status_code=500, detail="Internal server error")


# ── Dashboard ─────────────────────────────────────────────────────────────────

@app.get("/dashboard/summary")
def dashboard_summary():
    try:
        from services.shared.db import SessionLocal
        from services.shared.models import Video, LedgerWeek
        from sqlalchemy import func

        today = date.today()
        monday = today - timedelta(days=today.weekday())

        with SessionLocal() as session:
            # Pipeline snapshot: count videos by status
            status_counts = (
                session.query(Video.status, func.count(Video.id))
                .group_by(Video.status)
                .all()
            )
            pipeline = {s: c for s, c in status_counts}

            # Current week budget
            ledger = session.get(LedgerWeek, monday)
            budget = {
                "week_id": monday.isoformat(),
                "budget_limit": float(ledger.budget_limit) if ledger else 100.0,
                "planned_spend": float(ledger.planned_spend) if ledger else 0.0,
                "actual_spend": float(ledger.actual_spend) if ledger else 0.0,
            }

            # Videos still in production (not yet scheduled/published)
            in_production = (
                session.query(Video)
                .filter(Video.status.notin_(["SCHEDULED", "PUBLISHED"]))
                .order_by(Video.created_at.desc())
                .limit(10)
                .all()
            )
            queue = [{"id": v.id, "title": v.title, "status": v.status} for v in in_production]

        return {"pipeline": pipeline, "budget": budget, "queue": queue}
    except HTTPException:
        raise
    except Exception:
        _log.exception("Error in dashboard_summary")
        raise HTTPException(status_code=500, detail="Internal server error")


# ── ICS calendar feed ─────────────────────────────────────────────────────────

@app.get("/calendar.ics", response_class=PlainTextResponse)
def calendar_ics():
    try:
        from services.shared.db import SessionLocal
        from services.shared.models import Video

        with SessionLocal() as session:
            videos = session.query(Video).order_by(Video.created_at.desc()).limit(50).all()

        lines = [
            "BEGIN:VCALENDAR",
            "VERSION:2.0",
            "PRODID:-//Culinary AI//culinary-ai//EN",
            "CALSCALE:GREGORIAN",
            "METHOD:PUBLISH",
            "X-WR-CALNAME:Culinary AI Production",
            "X-WR-TIMEZONE:America/Montreal",
        ]

        for v in videos:
            if v.approved_at:
                # Scheduled/published: use approved_at as publish date
                dt = v.approved_at.strftime("%Y%m%dT%H%M%SZ")
                dt_end = (v.approved_at + timedelta(hours=1)).strftime("%Y%m%dT%H%M%SZ")
                summary = f"Publish: {v.title}"
            else:
                # In production: use created_at as shoot-planning reminder
                dt = v.created_at.strftime("%Y%m%dT%H%M%SZ")
                dt_end = (v.created_at + timedelta(hours=2)).strftime("%Y%m%dT%H%M%SZ")
                summary = f"[{v.status}] {v.title}"

            lines += [
                "BEGIN:VEVENT",
                f"UID:{v.id}@culinary-ai",
                f"DTSTART:{dt}",
                f"DTEND:{dt_end}",
                f"SUMMARY:{summary}",
                f"DESCRIPTION:Status: {v.status} | Stream: {v.stream}",
                "END:VEVENT",
            ]

        lines.append("END:VCALENDAR")
        return "\r\n".join(lines) + "\r\n"
    except HTTPException:
        raise
    except Exception:
        _log.exception("Error in calendar_ics")
        raise HTTPException(status_code=500, detail="Internal server error")


# ── Etienne: analytics ────────────────────────────────────────────────────────

@app.post("/etienne/metrics/{video_id}")
def etienne_save_metrics(video_id: str, body: MetricsIngest):
    _validate_uuid(video_id, "video_id")
    video = get_video(video_id)
    if not video:
        raise HTTPException(status_code=404, detail="video not found")
    metric_id = save_video_metric(
        video_id=video_id,
        platform=body.platform,
        views=body.views,
        watch_time_seconds=body.watch_time_seconds,
        retention_pct=body.retention_pct,
        likes=body.likes,
        comments=body.comments,
        shares=body.shares,
    )
    return {"metric_id": metric_id, "video_id": video_id}


@app.get("/etienne/metrics/{video_id}")
def etienne_get_metrics(video_id: str):
    _validate_uuid(video_id, "video_id")
    video = get_video(video_id)
    if not video:
        raise HTTPException(status_code=404, detail="video not found")
    return get_video_metrics(video_id)


@app.get("/etienne/report/{week_id}")
def etienne_weekly_report(week_id: str):
    try:
        week = _validate_date(week_id, "week_id")
        report = generate_weekly_report(week)
        return report.model_dump()
    except HTTPException:
        raise
    except Exception:
        _log.exception("Error in etienne_weekly_report")
        raise HTTPException(status_code=500, detail="Internal server error")


# ── Observability ─────────────────────────────────────────────────────────────

@app.get("/observability/costs")
def observability_costs():
    from datetime import timedelta
    today = date.today()
    monday = today - timedelta(days=today.weekday())
    return get_cost_summary(monday)


@app.get("/observability/latency")
def observability_latency():
    return get_latency_summary()


@app.get("/observability/slo")
def observability_slo():
    return get_slo_status()
