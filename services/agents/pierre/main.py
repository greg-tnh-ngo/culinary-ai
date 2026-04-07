# services/agents/pierre/main.py
import json, logging
from typing import Dict, List, Optional
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


class EditDirective(BaseModel):
    cut_cadence: Dict       # {"min_s": float, "max_s": float, "hook_s": float, "notes": str}
    captions: Dict          # {"wpm": int, "style": str, "safe_zone": str}
    audio: Dict             # {"dialog_lufs": float, "peak_dbfs": float, "music_duck_db": float, "room_tone_s": int}
    color: Dict             # {"lut": str, "wb_kelvin": int, "exposure_notes": str}
    format: Dict            # {"aspect": str, "resolution": str, "fps": int}
    texture_inserts: List[str]   # mandatory b-roll moments
    chapter_markers: List[Dict]  # [{"timecode": "0:00", "label": str}]
    notes: str


def _stub_impl(shoot_card: Dict, scripts: List[Dict]) -> EditDirective:
    # Extract shotlist names as texture insert suggestions when available
    shotlist = shoot_card.get("shotlist", [])
    texture_inserts = [s["name"] for s in shotlist if isinstance(s, dict) and "name" in s]
    if not texture_inserts:
        texture_inserts = ["close-up of ingredients", "hands in action", "finished plate overhead"]

    return EditDirective(
        cut_cadence={"min_s": 0.8, "max_s": 2.0, "hook_s": 1.5, "notes": "Hold hero shot for 2s minimum"},
        captions={"wpm": 105, "style": "white bold, black stroke 3px", "safe_zone": "bottom 20% — avoid last 150px"},
        audio={"dialog_lufs": -14, "peak_dbfs": -1, "music_duck_db": -7, "room_tone_s": 10},
        color={"lut": "neutral warm", "wb_kelvin": 5500, "exposure_notes": "lift shadows slightly; protect highlights on white plate"},
        format={"aspect": "9:16", "resolution": "1080x1920", "fps": 30},
        texture_inserts=texture_inserts,
        chapter_markers=[
            {"timecode": "0:00", "label": "Hook"},
            {"timecode": "0:05", "label": "Mise en place"},
            {"timecode": "0:20", "label": "Technique"},
            {"timecode": "0:50", "label": "Plate & CTA"},
        ],
        notes="Export H.264, 15 Mbps. Check captions don't overlap safe zone on TikTok.",
    )


_SYSTEM_PROMPT = (
    "You are Pierre, the editing director for a solo French cooking channel filming on iPhone 11. "
    "Given a shoot card and script, return ONLY a valid JSON object — no markdown, no explanation. "
    "The object must have these exact keys: "
    "cut_cadence (object with min_s float, max_s float, hook_s float, notes string), "
    "captions (object with wpm int, style string, safe_zone string), "
    "audio (object with dialog_lufs float, peak_dbfs float, music_duck_db float, room_tone_s int), "
    "color (object with lut string, wb_kelvin int, exposure_notes string), "
    "format (object with aspect string, resolution string, fps int), "
    "texture_inserts (array of strings — b-roll moments from the shotlist), "
    "chapter_markers (array of objects with timecode string and label string), "
    "notes (string). "
    "Rules: 9:16 master; cut cadence 0.8–2.0s; captions 90–120 wpm; dialog at -14 LUFS; "
    "peak -1 dBFS; music duck -6 to -9 dB under VO; export 1080x1920 H.264."
)


def _edit_directive_llm(shoot_card: Dict, scripts: List[Dict]) -> EditDirective:
    tutorial = next((s for s in scripts if s.get("variant") == "TUTORIAL"), scripts[0] if scripts else {})
    body = tutorial.get("body", "")
    shotlist = shoot_card.get("shotlist", [])

    user_content = f"Shotlist: {json.dumps(shotlist)}\n\nScript body:\n{body[:1500]}"
    msg = _CLIENT.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=2048,
        system=_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_content}],
    )
    raw = msg.content[0].text.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.strip()
    data = json.loads(raw)
    directive = EditDirective.model_validate(data)
    # Ensure texture_inserts is never empty — fall back to shotlist names or defaults
    if not directive.texture_inserts:
        shotlist = shoot_card.get("shotlist", [])
        directive.texture_inserts = (
            [s["name"] for s in shotlist if isinstance(s, dict) and "name" in s]
            or ["close-up of ingredients", "hands in action", "finished plate overhead"]
        )
    return directive


def make_edit_directive(shoot_card: Dict, scripts: List[Dict]) -> EditDirective:
    if not _LLM_AVAILABLE:
        return _stub_impl(shoot_card, scripts)
    try:
        return _edit_directive_llm(shoot_card, scripts)
    except Exception as e:
        _log.warning("Pierre LLM failed (%s: %s), falling back to stub", type(e).__name__, e)
        return _stub_impl(shoot_card, scripts)
