import json, logging
from pydantic import BaseModel
from typing import Literal, List, Dict, Optional
from services.shared.db import _cfg

_log = logging.getLogger(__name__)
try:
    import anthropic as _anthropic_mod
    _API_KEY = _cfg.ANTHROPIC_API_KEY
    _LLM_AVAILABLE = bool(_API_KEY)
    _CLIENT = _anthropic_mod.Anthropic(api_key=_API_KEY) if _LLM_AVAILABLE else None
except ImportError:
    _LLM_AVAILABLE = False
    _CLIENT = None


class IdeaCard(BaseModel):
    dish: str
    stream: Literal["SHORT", "LONG", "SHORT+LONG"]
    creative_spin: str
    production_difficulty: int  # 0..5
    culinary_complexity: int    # 0..5
    estimated_cost: float
    seasonality: Optional[str] = None
    inspiration: List[Dict]
    hooks: List[str]
    cta: List[str]
    plagiarism_score: float = 0.1


def _stub_impl() -> IdeaCard:
    return IdeaCard(
        dish="Omelette aux fines herbes",
        stream="SHORT",
        creative_spin="3-technique omelette: classic fold + chives oil finish",
        production_difficulty=1,
        culinary_complexity=2,
        estimated_cost=3.50,
        seasonality="spring",
        inspiration=[{"url": "https://example.com/omelette", "quoted": "Classic French technique with chives."}],
        hooks=["The 10-second French omelette test", "Your pan is too hot — fix it like this"],
        cta=["Save for breakfast tomorrow", "Try with fines herbes tonight"],
    )


def _curate_llm() -> IdeaCard:
    msg = _CLIENT.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=1024,
        system=(
            "You are Julien, the idea curator for a solo French cooking channel on TikTok and YouTube Shorts. "
            "Output ONLY a single JSON object, no markdown, no explanation. "
            "Fields: dish (string), stream (SHORT or LONG or SHORT+LONG), "
            "creative_spin (string — must name a concrete technique twist or cultural mashup, not a generic label), "
            "production_difficulty (int 0-5), culinary_complexity (int 0-5), estimated_cost (float USD), "
            "seasonality (string or null), "
            "inspiration (array of objects with url and quoted fields — at least 1), "
            "hooks (array of strings — at least 3 short overlay lines under 10 words each), "
            "cta (array of strings — at least 2 end-screen lines), "
            "plagiarism_score (float 0.0-1.0)."
        ),
        messages=[{"role": "user", "content": "Generate a fresh French cooking idea for a YouTube Short."}],
    )
    raw = msg.content[0].text.strip()
    # Strip markdown code fences if present
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.strip()
    _log.debug("Julien raw response: %s", raw[:200])
    data = json.loads(raw)
    return IdeaCard.model_validate(data)


def curate_stub() -> IdeaCard:
    if not _LLM_AVAILABLE:
        return _stub_impl()
    try:
        return _curate_llm()
    except Exception as e:
        _log.warning("Julien LLM failed (%s: %s), falling back to stub", type(e).__name__, e)
        return _stub_impl()
