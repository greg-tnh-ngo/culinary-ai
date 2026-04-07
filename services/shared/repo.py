# services/shared/repo.py
from __future__ import annotations
import uuid
from services.shared.db import SessionLocal, with_retry
from datetime import datetime, timezone, date
from decimal import Decimal
from services.shared.models import PipelineRun, Video, Script, VideoStatus, Ingredient, Recipe, RecipeIngredient, LedgerWeek, Purchase, VideoMetric


def save_pipeline_run(kind: str, idea: dict, scripts: list[dict], shoot_card: dict) -> int:
    def _run():
        with SessionLocal() as session:
            row = PipelineRun(
                kind=kind,
                idea=idea,
                scripts={"items": scripts},
                shoot_card=shoot_card,
            )
            session.add(row)
            session.commit()
            session.refresh(row)
            return row.id
    return with_retry(_run)


def get_pipeline_run(run_id: int) -> dict | None:
    with SessionLocal() as session:
        row = session.get(PipelineRun, run_id)
        if not row:
            return None
        return {
            "id": row.id,
            "kind": row.kind,
            "idea": row.idea,
            "scripts": row.scripts,
            "shoot_card": row.shoot_card,
            "created_at": row.created_at.isoformat(),
        }


def create_video(title: str, stream: str) -> str:
    def _run():
        with SessionLocal() as session:
            row = Video(
                id=str(uuid.uuid4()),
                title=title,
                stream=stream,
                status=VideoStatus.IDEA,
            )
            session.add(row)
            session.commit()
            session.refresh(row)
            return row.id
    return with_retry(_run)


def update_video_status(video_id: str, status: str) -> None:
    def _run():
        with SessionLocal() as session:
            row = session.get(Video, video_id)
            if row:
                row.status = status
                session.commit()
    return with_retry(_run)


def save_script(video_id: str, variant: str, body: str, verification: dict | None = None, chapters: list[dict] | None = None) -> str:
    def _run():
        with SessionLocal() as session:
            row = Script(
                id=str(uuid.uuid4()),
                video_id=video_id,
                variant=variant,
                body=body,
                verification=verification,
                chapters=chapters,
            )
            session.add(row)
            session.commit()
            session.refresh(row)
            return row.id
    return with_retry(_run)


def get_video(video_id: str) -> dict | None:
    with SessionLocal() as session:
        row = session.get(Video, video_id)
        if not row:
            return None
        scripts = [
            {
                "id": s.id,
                "variant": s.variant,
                "body": s.body,
                "verification": s.verification,
                "created_at": s.created_at.isoformat(),
            }
            for s in row.scripts
        ]
        return {
            "id": row.id,
            "title": row.title,
            "stream": row.stream,
            "status": row.status,
            "created_at": row.created_at.isoformat(),
            "approved_at": row.approved_at.isoformat() if row.approved_at else None,
            "release_packet": row.release_packet,
            "feedback": row.feedback,
            "scripts": scripts,
        }


def save_release_packet(video_id: str, release_packet: dict) -> None:
    def _run():
        with SessionLocal() as session:
            row = session.get(Video, video_id)
            if row:
                row.release_packet = release_packet
                session.commit()
    return with_retry(_run)


def approve_video(video_id: str) -> dict | None:
    def _run():
        with SessionLocal() as session:
            row = session.get(Video, video_id)
            if not row:
                return None
            row.status = VideoStatus.SCHEDULED
            row.approved_at = datetime.now(timezone.utc)
            row.feedback = None
            session.commit()
            return row.release_packet
    return with_retry(_run)


def request_changes(video_id: str, feedback: str) -> None:
    with SessionLocal() as session:
        row = session.get(Video, video_id)
        if row:
            row.status = VideoStatus.SCRIPT
            row.feedback = feedback
            session.commit()


def force_set_video_status(video_id: str, status: str) -> bool:
    with SessionLocal() as session:
        row = session.get(Video, video_id)
        if not row:
            return False
        row.status = status
        session.commit()
        return True


def save_idea_draft(idea: dict) -> str:
    def _run():
        with SessionLocal() as session:
            row = Video(
                id=str(uuid.uuid4()),
                title=idea.get("title", "Draft"),
                stream=idea.get("stream", "SHORT"),
                status=VideoStatus.IDEA,
                idea_draft=idea,
            )
            session.add(row)
            session.commit()
            session.refresh(row)
            return row.id
    return with_retry(_run)


def list_videos() -> list[dict]:
    with SessionLocal() as session:
        rows = session.query(Video).order_by(Video.created_at.desc()).all()
        return [
            {
                "id": r.id,
                "title": r.title,
                "stream": r.stream,
                "status": r.status,
                "created_at": r.created_at.isoformat(),
            }
            for r in rows
        ]


# ── Armand: ingredients ───────────────────────────────────────────────────────

def list_ingredients() -> list[dict]:
    with SessionLocal() as session:
        rows = session.query(Ingredient).order_by(Ingredient.name).all()
        return [
            {
                "id": r.id,
                "name": r.name,
                "category": r.category,
                "unit": r.unit,
                "avg_price_per_unit": float(r.avg_price_per_unit) if r.avg_price_per_unit else None,
                "current_qty": float(r.current_qty),
                "expiry_date": r.expiry_date.isoformat() if r.expiry_date else None,
            }
            for r in rows
        ]


def create_ingredient(name: str, category: str | None, unit: str | None, avg_price_per_unit: float | None) -> str:
    with SessionLocal() as session:
        row = Ingredient(
            id=str(uuid.uuid4()),
            name=name,
            category=category,
            unit=unit,
            avg_price_per_unit=Decimal(str(avg_price_per_unit)) if avg_price_per_unit else None,
        )
        session.add(row)
        session.commit()
        session.refresh(row)
        return row.id


def get_ingredient_by_name(name: str) -> dict | None:
    with SessionLocal() as session:
        row = session.query(Ingredient).filter(Ingredient.name == name).first()
        if not row:
            return None
        return {
            "id": row.id,
            "name": row.name,
            "category": row.category,
            "unit": row.unit,
            "avg_price_per_unit": float(row.avg_price_per_unit) if row.avg_price_per_unit else None,
            "current_qty": float(row.current_qty),
        }


def update_ingredient_qty(ingredient_id: str, delta: float) -> None:
    with SessionLocal() as session:
        row = session.get(Ingredient, ingredient_id)
        if row:
            row.current_qty = Decimal(str(float(row.current_qty) + delta))
            session.commit()


def upsert_ingredient_price(ingredient_id: str, avg_price: float) -> None:
    with SessionLocal() as session:
        row = session.get(Ingredient, ingredient_id)
        if row:
            row.avg_price_per_unit = Decimal(str(avg_price))
            session.commit()


def update_ingredient(ingredient_id: str, **fields) -> dict | None:
    with SessionLocal() as session:
        row = session.get(Ingredient, ingredient_id)
        if not row:
            return None
        if "name" in fields:
            row.name = fields["name"]
        if "category" in fields:
            row.category = fields["category"]
        if "unit" in fields:
            row.unit = fields["unit"]
        if "avg_price_per_unit" in fields and fields["avg_price_per_unit"] is not None:
            row.avg_price_per_unit = Decimal(str(fields["avg_price_per_unit"]))
        session.commit()
        session.refresh(row)
        return {
            "id": row.id,
            "name": row.name,
            "category": row.category,
            "unit": row.unit,
            "avg_price_per_unit": float(row.avg_price_per_unit) if row.avg_price_per_unit else None,
            "current_qty": float(row.current_qty),
            "expiry_date": row.expiry_date.isoformat() if row.expiry_date else None,
        }


def delete_ingredient(ingredient_id: str) -> bool:
    with SessionLocal() as session:
        row = session.get(Ingredient, ingredient_id)
        if not row:
            return False
        session.delete(row)
        session.commit()
        return True


# ── Armand: recipes ───────────────────────────────────────────────────────────

def list_recipes() -> list[dict]:
    with SessionLocal() as session:
        rows = session.query(Recipe).order_by(Recipe.title).all()
        return [{"id": r.id, "title": r.title, "difficulty": r.difficulty, "stream": r.stream} for r in rows]


def create_recipe(title: str, difficulty: int | None, time_required_minutes: int | None, stream: str | None) -> str:
    with SessionLocal() as session:
        row = Recipe(id=str(uuid.uuid4()), title=title, difficulty=difficulty,
                     time_required_minutes=time_required_minutes, stream=stream)
        session.add(row)
        session.commit()
        session.refresh(row)
        return row.id


def add_recipe_ingredient(recipe_id: str, ingredient_id: str, qty: float | None) -> None:
    with SessionLocal() as session:
        row = RecipeIngredient(
            recipe_id=recipe_id,
            ingredient_id=ingredient_id,
            qty=Decimal(str(qty)) if qty is not None else None,
        )
        session.add(row)
        session.commit()


def update_recipe(recipe_id: str, **fields) -> dict | None:
    with SessionLocal() as session:
        row = session.get(Recipe, recipe_id)
        if not row:
            return None
        for f in ("title", "difficulty", "time_required_minutes", "stream"):
            if f in fields:
                setattr(row, f, fields[f])
        if "ingredients" in fields and fields["ingredients"] is not None:
            session.query(RecipeIngredient).filter(RecipeIngredient.recipe_id == recipe_id).delete()
            for ing in fields["ingredients"]:
                ri = RecipeIngredient(
                    recipe_id=recipe_id,
                    ingredient_id=ing["ingredient_id"],
                    qty=Decimal(str(ing["qty"])) if ing.get("qty") is not None else None,
                )
                session.add(ri)
        session.commit()
        session.refresh(row)
        return {"id": row.id, "title": row.title, "difficulty": row.difficulty,
                "time_required_minutes": row.time_required_minutes, "stream": row.stream}


def delete_recipe(recipe_id: str) -> bool:
    with SessionLocal() as session:
        row = session.get(Recipe, recipe_id)
        if not row:
            return False
        session.query(RecipeIngredient).filter(RecipeIngredient.recipe_id == recipe_id).delete()
        session.delete(row)
        session.commit()
        return True


def get_recipe_with_ingredients(recipe_id: str) -> dict | None:
    with SessionLocal() as session:
        recipe = session.get(Recipe, recipe_id)
        if not recipe:
            return None
        ris = session.query(RecipeIngredient).filter(RecipeIngredient.recipe_id == recipe_id).all()
        lines = []
        for ri in ris:
            ing = session.get(Ingredient, ri.ingredient_id)
            if ing:
                lines.append({
                    "ingredient_id": ing.id,
                    "name": ing.name,
                    "qty_needed": float(ri.qty) if ri.qty else None,
                    "unit": ing.unit,
                    "avg_price_per_unit": float(ing.avg_price_per_unit) if ing.avg_price_per_unit else None,
                    "current_qty": float(ing.current_qty),
                })
        return {"id": recipe.id, "title": recipe.title, "difficulty": recipe.difficulty,
                "stream": recipe.stream, "ingredients": lines}


# ── Armand: ledger ────────────────────────────────────────────────────────────

def get_or_create_ledger_week(week_id: date) -> dict:
    def _run():
        with SessionLocal() as session:
            row = session.get(LedgerWeek, week_id)
            if not row:
                row = LedgerWeek(week_id=week_id)
                session.add(row)
                session.commit()
                session.refresh(row)
            return {
                "week_id": row.week_id.isoformat(),
                "budget_limit": float(row.budget_limit),
                "planned_spend": float(row.planned_spend),
                "actual_spend": float(row.actual_spend),
            }
    return with_retry(_run)


def update_ledger_planned(week_id: date, amount: float, recipe_ids: list[str] | None = None) -> None:
    with SessionLocal() as session:
        row = session.get(LedgerWeek, week_id)
        if not row:
            row = LedgerWeek(week_id=week_id)
            session.add(row)
        row.planned_spend = Decimal(str(amount))
        if recipe_ids is not None:
            row.planned_recipe_ids = {"ids": recipe_ids}
        session.commit()


def update_ledger_actual(week_id: date, delta: float) -> None:
    with SessionLocal() as session:
        row = session.get(LedgerWeek, week_id)
        if not row:
            row = LedgerWeek(week_id=week_id)
            session.add(row)
        row.actual_spend = Decimal(str(float(row.actual_spend) + delta))
        session.commit()


def get_grocery_list(week_id: date) -> dict:
    """Return aggregated shopping list for a week based on planned recipes."""
    with SessionLocal() as session:
        ledger = session.get(LedgerWeek, week_id)
        if not ledger or not ledger.planned_recipe_ids:
            return {"recipe_ids": [], "items": []}
        recipe_ids = ledger.planned_recipe_ids.get("ids", [])

        # Aggregate qty_needed per ingredient across all recipes
        aggregated: dict[str, dict] = {}  # ingredient_id → aggregated data
        recipe_titles = []
        for rid in recipe_ids:
            recipe = session.get(Recipe, rid)
            if not recipe:
                continue
            recipe_titles.append(recipe.title)
            ris = session.query(RecipeIngredient).filter(RecipeIngredient.recipe_id == rid).all()
            for ri in ris:
                ing = session.get(Ingredient, ri.ingredient_id)
                if not ing:
                    continue
                qty = float(ri.qty) if ri.qty else 0.0
                if ing.id not in aggregated:
                    aggregated[ing.id] = {
                        "ingredient_id": ing.id,
                        "name": ing.name,
                        "category": ing.category,
                        "unit": ing.unit,
                        "qty_needed": 0.0,
                        "in_stock": float(ing.current_qty),
                        "unit_price": float(ing.avg_price_per_unit) if ing.avg_price_per_unit else None,
                    }
                aggregated[ing.id]["qty_needed"] += qty

        items = []
        for item in aggregated.values():
            to_buy = max(0.0, item["qty_needed"] - item["in_stock"])
            unit_price = item["unit_price"] or 0.0
            items.append({
                **item,
                "to_buy": round(to_buy, 4),
                "estimated_cost": round(to_buy * unit_price, 2),
            })
        # Only include items that need to be bought
        shopping = [i for i in items if i["to_buy"] > 0]
        return {
            "recipe_ids": recipe_ids,
            "recipe_titles": recipe_titles,
            "items": shopping,
            "total_estimated_cost": round(sum(i["estimated_cost"] for i in shopping), 2),
        }


# ── Armand: purchases ─────────────────────────────────────────────────────────

def save_purchase(occurred_at: datetime, store: str | None, items: list[dict], total: float) -> str:
    with SessionLocal() as session:
        row = Purchase(
            id=str(uuid.uuid4()),
            occurred_at=occurred_at,
            store=store,
            items={"items": items},
            total=Decimal(str(total)),
        )
        session.add(row)
        session.commit()
        session.refresh(row)
        return row.id


# ── Etienne: video metrics ────────────────────────────────────────────────────

def save_video_metric(
    video_id: str,
    platform: str,
    views: int = 0,
    watch_time_seconds: int = 0,
    retention_pct: float = 0.0,
    likes: int = 0,
    comments: int = 0,
    shares: int = 0,
) -> str:
    def _run():
        with SessionLocal() as session:
            row = VideoMetric(
                id=str(uuid.uuid4()),
                video_id=video_id,
                platform=platform,
                views=views,
                watch_time_seconds=watch_time_seconds,
                retention_pct=Decimal(str(retention_pct)),
                likes=likes,
                comments=comments,
                shares=shares,
            )
            session.add(row)
            session.commit()
            session.refresh(row)
            return row.id
    return with_retry(_run)


def get_video_metrics(video_id: str) -> list[dict]:
    with SessionLocal() as session:
        rows = session.query(VideoMetric).filter(
            VideoMetric.video_id == video_id
        ).order_by(VideoMetric.recorded_at.desc()).all()
        return [
            {
                "id": r.id,
                "video_id": r.video_id,
                "recorded_at": r.recorded_at.isoformat(),
                "platform": r.platform,
                "views": r.views,
                "watch_time_seconds": r.watch_time_seconds,
                "retention_pct": float(r.retention_pct),
                "likes": r.likes,
                "comments": r.comments,
                "shares": r.shares,
            }
            for r in rows
        ]


def get_weekly_metrics_summary(week_start: date, week_end: date) -> list[dict]:
    """Return latest metric snapshot per video for the given week range."""
    from sqlalchemy import func
    with SessionLocal() as session:
        # Get the most recent metric per (video_id, platform) recorded in the week
        subq = (
            session.query(
                VideoMetric.video_id,
                VideoMetric.platform,
                func.max(VideoMetric.recorded_at).label("max_recorded_at"),
            )
            .filter(
                VideoMetric.recorded_at >= week_start,
                VideoMetric.recorded_at < week_end,
            )
            .group_by(VideoMetric.video_id, VideoMetric.platform)
            .subquery()
        )
        rows = (
            session.query(VideoMetric, Video.title)
            .join(subq, (VideoMetric.video_id == subq.c.video_id) &
                        (VideoMetric.platform == subq.c.platform) &
                        (VideoMetric.recorded_at == subq.c.max_recorded_at))
            .join(Video, Video.id == VideoMetric.video_id)
            .all()
        )
        return [
            {
                "video_id": m.video_id,
                "title": title,
                "platform": m.platform,
                "views": m.views,
                "watch_time_seconds": m.watch_time_seconds,
                "retention_pct": float(m.retention_pct),
                "likes": m.likes,
                "comments": m.comments,
                "shares": m.shares,
            }
            for m, title in rows
        ]


# ── Observability ─────────────────────────────────────────────────────────────

def record_llm_call(
    agent: str,
    model: str,
    input_tokens: int,
    output_tokens: int,
    cost_usd: float,
    duration_ms: int,
    succeeded: bool,
) -> None:
    def _run():
        from services.shared.models import LlmCall
        with SessionLocal() as session:
            row = LlmCall(
                agent=agent,
                model=model,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cost_usd=Decimal(str(cost_usd)),
                duration_ms=duration_ms,
                succeeded=succeeded,
            )
            session.add(row)
            session.commit()
    return with_retry(_run)


def record_request_log(
    endpoint: str,
    method: str,
    status_code: int,
    duration_ms: int,
) -> None:
    def _run():
        from services.shared.models import RequestLog
        with SessionLocal() as session:
            row = RequestLog(
                endpoint=endpoint,
                method=method,
                status_code=status_code,
                duration_ms=duration_ms,
            )
            session.add(row)
            session.commit()
    return with_retry(_run)


def get_cost_summary(since_date: date) -> dict:
    from services.shared.models import LlmCall
    from sqlalchemy import func
    with SessionLocal() as session:
        rows = (
            session.query(
                LlmCall.agent,
                func.sum(LlmCall.cost_usd).label("total_cost"),
                func.sum(LlmCall.input_tokens).label("total_input"),
                func.sum(LlmCall.output_tokens).label("total_output"),
                func.count(LlmCall.id).label("call_count"),
            )
            .filter(LlmCall.created_at >= since_date)
            .group_by(LlmCall.agent)
            .all()
        )
        by_agent = [
            {
                "agent": r.agent,
                "cost_usd": round(float(r.total_cost), 6),
                "input_tokens": r.total_input,
                "output_tokens": r.total_output,
                "call_count": r.call_count,
            }
            for r in rows
        ]
        total = round(sum(a["cost_usd"] for a in by_agent), 6)
        return {"since": since_date.isoformat(), "total_cost_usd": total, "by_agent": by_agent}


def get_latency_summary() -> list[dict]:
    from services.shared.models import RequestLog
    from sqlalchemy import text
    from datetime import timedelta
    since = datetime.utcnow() - timedelta(days=7)
    with SessionLocal() as session:
        result = session.execute(
            text("""
                SELECT
                    endpoint,
                    method,
                    COUNT(*) AS request_count,
                    PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY duration_ms) AS p50_ms,
                    PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY duration_ms) AS p95_ms
                FROM request_log
                WHERE created_at >= :since
                GROUP BY endpoint, method
                ORDER BY endpoint, method
            """),
            {"since": since},
        )
        return [
            {
                "endpoint": r.endpoint,
                "method": r.method,
                "request_count": r.request_count,
                "p50_ms": round(r.p50_ms, 1) if r.p50_ms is not None else None,
                "p95_ms": round(r.p95_ms, 1) if r.p95_ms is not None else None,
            }
            for r in result
        ]


def get_slo_status() -> list[dict]:
    from services.shared.models import LlmCall, RequestLog, Video, LedgerWeek
    from sqlalchemy import func, text
    from datetime import timedelta

    today = date.today()
    monday = today - timedelta(days=today.weekday())
    seven_days_ago = datetime.utcnow() - timedelta(days=7)
    results = []

    with SessionLocal() as session:
        # SLO 1: Budget
        ledger = session.get(LedgerWeek, monday)
        if ledger:
            actual = float(ledger.actual_spend)
            limit = float(ledger.budget_limit)
        else:
            actual, limit = 0.0, 100.0
        results.append({
            "name": "budget",
            "description": "Weekly actual_spend <= budget_limit",
            "passing": actual <= limit,
            "current_value": actual,
            "threshold": limit,
            "unit": "usd",
        })

        # SLO 2: LLM reliability
        total_calls = session.query(func.count(LlmCall.id)).filter(
            LlmCall.created_at >= seven_days_ago
        ).scalar() or 0
        succeeded_calls = session.query(func.count(LlmCall.id)).filter(
            LlmCall.created_at >= seven_days_ago,
            LlmCall.succeeded.is_(True),
        ).scalar() or 0
        reliability = (succeeded_calls / total_calls) if total_calls > 0 else 1.0
        results.append({
            "name": "llm_reliability",
            "description": "LLM success rate >= 90% (last 7 days)",
            "passing": reliability >= 0.90,
            "current_value": round(reliability * 100, 1),
            "threshold": 90.0,
            "unit": "percent",
        })

        # SLO 3: Pipeline throughput
        scheduled_count = session.query(func.count(Video.id)).filter(
            Video.status == "SCHEDULED",
            Video.approved_at >= seven_days_ago,
        ).scalar() or 0
        results.append({
            "name": "pipeline_throughput",
            "description": ">= 1 video SCHEDULED in last 7 days",
            "passing": scheduled_count >= 1,
            "current_value": scheduled_count,
            "threshold": 1,
            "unit": "videos",
        })

        # SLO 4: Short pipeline p95 latency
        p95_row = session.execute(
            text("""
                SELECT PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY duration_ms) AS p95
                FROM request_log
                WHERE endpoint = '/pipeline/short/run'
                  AND created_at >= :since
            """),
            {"since": seven_days_ago},
        ).first()
        p95_ms = float(p95_row.p95) if p95_row and p95_row.p95 is not None else None
        results.append({
            "name": "short_pipeline_latency",
            "description": "POST /pipeline/short/run p95 <= 30s (last 7 days)",
            "passing": (p95_ms is None) or (p95_ms <= 30_000),
            "current_value": p95_ms,
            "threshold": 30_000,
            "unit": "ms",
        })

    return results
