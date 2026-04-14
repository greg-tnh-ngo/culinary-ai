# services/agents/etienne/main.py
import json, logging
from datetime import date, timedelta
from typing import List, Optional
from pydantic import BaseModel
from services.shared.db import _cfg

_log = logging.getLogger(__name__)
try:
    from services.shared.llm_client import get_llm as _get_llm
    _CLIENT, _MODEL = _get_llm("etienne")
    _LLM_AVAILABLE = _CLIENT is not None
except Exception:
    _CLIENT, _MODEL, _LLM_AVAILABLE = None, "claude-haiku-4-5-20251001", False


class VideoStat(BaseModel):
    video_id: str
    title: str
    platform: str
    views: int
    watch_time_seconds: int
    retention_pct: float
    likes: int
    comments: int
    shares: int


class WeeklyReport(BaseModel):
    week_id: str                        # ISO date — Monday of the week
    top_performers: List[VideoStat]     # sorted by views desc
    total_views: int
    avg_retention_pct: float
    budget_spent: float
    budget_remaining: float
    insights: List[str]                 # LLM-generated narrative bullets
    recommendations: List[str]          # LLM-generated action items


def _current_monday() -> date:
    today = date.today()
    return today - timedelta(days=today.weekday())


def generate_weekly_report(week_id: Optional[date] = None) -> WeeklyReport:
    from services.shared.repo import get_weekly_metrics_summary, get_or_create_ledger_week
    if week_id is None:
        week_id = _current_monday()

    week_end = week_id + timedelta(days=7)
    stats_raw = get_weekly_metrics_summary(week_id, week_end)
    ledger = get_or_create_ledger_week(week_id)

    stats = [VideoStat(**s) for s in stats_raw]
    stats.sort(key=lambda s: s.views, reverse=True)

    total_views = sum(s.views for s in stats)
    avg_retention = (
        round(sum(s.retention_pct for s in stats) / len(stats), 1)
        if stats else 0.0
    )
    budget_spent = ledger["actual_spend"]
    budget_remaining = round(ledger["budget_limit"] - budget_spent, 2)

    if _LLM_AVAILABLE and stats:
        insights, recommendations = _generate_insights_llm(
            stats, total_views, avg_retention, budget_spent, budget_remaining, week_id
        )
    else:
        insights, recommendations = _stub_insights(stats, total_views, avg_retention)

    return WeeklyReport(
        week_id=week_id.isoformat(),
        top_performers=stats[:5],
        total_views=total_views,
        avg_retention_pct=avg_retention,
        budget_spent=budget_spent,
        budget_remaining=budget_remaining,
        insights=insights,
        recommendations=recommendations,
    )


def _stub_insights(stats: List[VideoStat], total_views: int, avg_retention: float):
    if not stats:
        return (
            ["No video metrics recorded this week."],
            ["Record metrics after publishing videos to unlock insights."],
        )
    top = stats[0]
    insights = [
        f"{total_views} total views across {len(stats)} video(s) this week.",
        f"Average retention: {avg_retention:.1f}%.",
        f"Top performer: '{top.title}' on {top.platform} with {top.views} views.",
    ]
    recommendations = [
        "Add YouTube Analytics data via POST /etienne/metrics/{video_id} for AI insights.",
    ]
    return insights, recommendations


_SYSTEM_PROMPT = (
    "You are Etienne, the analytics advisor for a solo French cooking channel. "
    "Given a week's video performance metrics, write a concise weekly 1-pager. "
    "Return ONLY valid JSON with two keys: "
    "\"insights\" (array of 3–5 strings — key observations about what worked and why), "
    "\"recommendations\" (array of 2–4 strings — specific, actionable next steps). "
    "No markdown. No preamble. Focus on retention curves, hook performance, and budget efficiency. "
    "Be specific — name the videos and metrics. Speak to a solo creator, not a team."
)


def _generate_insights_llm(
    stats: List[VideoStat],
    total_views: int,
    avg_retention: float,
    budget_spent: float,
    budget_remaining: float,
    week_id: date,
) -> tuple[List[str], List[str]]:
    stats_text = "\n".join(
        f"- '{s.title}' ({s.platform}): {s.views} views, "
        f"{s.retention_pct:.1f}% retention, {s.likes} likes, "
        f"{s.watch_time_seconds}s watch time"
        for s in stats
    )
    user_content = (
        f"Week: {week_id.isoformat()}\n"
        f"Total views: {total_views}\n"
        f"Avg retention: {avg_retention:.1f}%\n"
        f"Budget spent: ${budget_spent:.2f} / remaining: ${budget_remaining:.2f}\n\n"
        f"Video stats:\n{stats_text}\n\n"
        "Write the weekly 1-pager."
    )
    try:
        msg = _CLIENT.messages.create(
            model=_MODEL,
            max_tokens=1024,
            system=_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_content}],
        )
        raw = msg.content[0].text.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
            raw = raw.strip()
        parsed = json.loads(raw)
        return parsed.get("insights", []), parsed.get("recommendations", [])
    except Exception as e:
        _log.warning("Etienne LLM failed: %s", e)
        return _stub_insights(stats, total_views, avg_retention)
