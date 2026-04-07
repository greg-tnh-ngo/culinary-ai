# services/agents/lucien/main.py
import json, logging
from typing import Dict, List
from pydantic import BaseModel
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


class PlatformVariant(BaseModel):
    platform: str           # "tiktok" or "instagram"
    hook: str               # adapted opening hook (≤5 words for TikTok, ≤8 for IG)
    caption: str            # platform-appropriate caption
    hashtags: List[str]     # 3–5 platform-specific hashtags
    safe_zone_notes: str    # UI element safe zones for that platform
    rationale: str          # SEO/engagement rationale


class PlatformPacket(BaseModel):
    video_id: str
    variants: List[PlatformVariant]  # one per platform (tiktok, instagram)


def _stub_impl(video_id: str, release_packet: Dict) -> PlatformPacket:
    youtube_assets = release_packet.get("assets", [])
    yt = youtube_assets[0] if youtube_assets else {}
    title = yt.get("title", "French cooking technique")
    return PlatformPacket(
        video_id=video_id,
        variants=[
            PlatformVariant(
                platform="tiktok",
                hook="Watch this.",
                caption=f"{title} #fyp",
                hashtags=["#fyp", "#frenchcooking", "#cookingtips", "#foodtok", "#cheftok"],
                safe_zone_notes="Keep text above bottom 20% (TikTok UI bar). Avoid top 8% (status bar). Left/right margins 4%.",
                rationale="Short hook drives 3s retention. #fyp maximises For You Page reach.",
            ),
            PlatformVariant(
                platform="instagram",
                hook="The technique most miss.",
                caption=f"{title}\n\nSave this for your next cook. Follow for more French technique.",
                hashtags=["#frenchcooking", "#reels", "#cookingreels", "#foodreels", "#cheflife"],
                safe_zone_notes="Keep text within centre 80% width. Avoid top 12% and bottom 15% (IG Reels UI). Use on-screen text at 30–70% height.",
                rationale="Save rate is IG's top signal. Caption drives follow CTA.",
            ),
        ],
    )


_SYSTEM_PROMPT = (
    "You are Lucien, the cross-platform adaptation specialist for a solo French cooking channel. "
    "Given a YouTube-optimized release packet, adapt the content for TikTok and Instagram Reels. "
    "Return ONLY a valid JSON array of exactly 2 objects — no markdown, no explanation. "
    "Each object has: "
    "platform (string: 'tiktok' or 'instagram'), "
    "hook (string — opening hook adapted for platform: TikTok ≤5 words, Instagram ≤8 words), "
    "caption (string — TikTok: ≤150 chars punchy; Instagram: 2–3 sentences + save CTA), "
    "hashtags (array of 3–5 strings with # prefix, platform-native), "
    "safe_zone_notes (string — specific pixel/percentage safe zone guidance for that platform's UI overlay), "
    "rationale (string — 1 sentence explaining the SEO or engagement reasoning for these choices). "
    "TikTok rules: hook under 5 words, caption casual and punchy, #fyp mandatory, avoid links. "
    "Instagram rules: hook under 8 words, caption can be longer, end with save CTA, mix niche and broad hashtags."
)


def _adapt_llm(video_id: str, release_packet: Dict) -> PlatformPacket:
    youtube_assets = release_packet.get("assets", [])
    user_content = (
        f"YouTube assets:\n{json.dumps(youtube_assets)}\n\n"
        f"QC notes: plagiarism_score={release_packet.get('qc', {}).get('plagiarism_score', 0)}"
    )
    msg = _CLIENT.messages.create(
        model="claude-haiku-4-5-20251001",
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
    variants = [PlatformVariant.model_validate(v) for v in json.loads(raw)]
    return PlatformPacket(video_id=video_id, variants=variants)


def adapt_for_platforms(video_id: str, release_packet: Dict) -> PlatformPacket:
    if not _LLM_AVAILABLE:
        return _stub_impl(video_id, release_packet)
    try:
        return _adapt_llm(video_id, release_packet)
    except Exception as e:
        _log.warning("Lucien LLM failed (%s: %s), falling back to stub", type(e).__name__, e)
        return _stub_impl(video_id, release_packet)
