# services/agents/marcel/main.py
import json, logging
from typing import Dict, List, Optional
from pydantic import BaseModel
from services.shared.db import _cfg

_log = logging.getLogger(__name__)
try:
    from services.shared.llm_client import get_llm as _get_llm
    from services.shared.llm_tracker import tracked_create as _tracked_create
    _CLIENT, _MODEL = _get_llm("marcel")                   # sonnet-tier: scripts
    _CLIENT_FAST, _MODEL_FAST = _get_llm("marcel", tier="fast")  # haiku-tier: chapters
    _LLM_AVAILABLE = _CLIENT is not None
except Exception:
    _CLIENT, _MODEL, _LLM_AVAILABLE = None, "claude-sonnet-4-6", False
    _CLIENT_FAST, _MODEL_FAST = None, "claude-haiku-4-5-20251001"
    _tracked_create = None


class TempEntry(BaseModel):
    claim: str
    value_celsius: float
    source: str

class RatioEntry(BaseModel):
    claim: str
    ratio: str
    source: str

class ClaimEntry(BaseModel):
    statement: str
    verified: bool
    reference: str

class VerificationJSON(BaseModel):
    temps: List[TempEntry]
    ratios: List[RatioEntry]
    claims: List[ClaimEntry]


class Chapter(BaseModel):
    title: str
    duration_minutes: int       # target duration for this chapter
    key_points: List[str]       # 2–4 bullet points
    technique_focus: str        # core French technique highlighted


class ScriptOut(BaseModel):
    variant: str
    body: str
    hook_options: List[str] = []
    verification: Optional[Dict] = None
    chapters: Optional[List[Chapter]] = None   # populated for LONG-stream scripts only


_SYSTEM_PROMPT = (
    "You are Marcel, the scriptwriter for a solo French cooking channel. The host films alone on an iPhone and speaks directly to camera.\n\n"
    'Return ONLY valid JSON with this exact structure, no markdown, no commentary:\n'
    '{"TUTORIAL": {"hook_options": ["...", "...", "..."], "body": "...", "verification": {}}, '
    '"PERSONAL": {"hook_options": ["...", "...", "..."], "body": "...", "verification": {}}}\n\n'
    "VARIANT DEFINITIONS:\n"
    "- TUTORIAL: Educational, technique-first. Every step has a why. Tone: calm, precise, authoritative. Structure: hook, mise en place, technique step 1, technique step 2, plating, CTA.\n"
    "- PERSONAL: Story-first. Opens with a memory, emotion, or failure. Recipe is the vehicle. Structure: personal hook, story beat, recipe woven in, reflection, CTA.\n\n"
    "hook_options: exactly 3 alternative opening lines per variant.\n"
    "body: full script with stage directions in [square brackets]. SHORT = 60-90 seconds at 140wpm meaning 140-210 spoken words.\n\n"
    "STYLE RULES:\n"
    "1. Sentences under 15 words.\n"
    "2. Name technique in French first, then English: La liaison means this is how you bind a sauce without lumps.\n"
    "3. Never say guys, y'all, or amazing. Use this, here, watch.\n"
    "4. Stage directions in [square brackets].\n"
    "5. Address viewer as you directly.\n\n"
    "VERIFICATION: every variant must include a verification object:\n"
    '{"temps": [{"claim": "sentence from script", "value_celsius": 180, "source": "book or URL not Wikipedia"}], '
    '"ratios": [{"claim": "sentence", "ratio": "3:1", "source": "..."}], '
    '"claims": [{"statement": "factual assertion", "verified": true, "reference": "source"}]}\n'
    "Minimum per variant: 1 temp, 1 ratio, 2 claims. All sources must be non-Wikipedia culinary references."
)


def _stub_impl(idea: Dict, personal_prompts: Optional[Dict] = None) -> List[ScriptOut]:
    """Minimal stub for debugging import issues."""
    dish = idea.get("dish", idea.get("title", "Plat français"))
    return [
        ScriptOut(variant="TUTORIAL", body=f"Today we cook {dish}. Steps: prep → heat → butter."),
        ScriptOut(variant="PERSONAL", body=f"[Your story about {dish}] Then show your key technique.")
    ]


def _generate_chapters(idea: Dict, scripts: List[ScriptOut]) -> List[Chapter]:
    tutorial = next((s for s in scripts if s.variant == "TUTORIAL"), None)
    if _LLM_AVAILABLE and tutorial:
        return _chapters_llm(idea, tutorial.body)
    return _chapters_stub(idea)


def _chapters_stub(idea: Dict) -> List[Chapter]:
    dish = idea.get("dish", idea.get("title", "French dish"))
    return [
        Chapter(title="Introduction & mise en place", duration_minutes=3,
                key_points=["Equipment needed", "Ingredient prep", "Why this technique matters"],
                technique_focus="Mise en place"),
        Chapter(title=f"Core technique — {dish}", duration_minutes=6,
                key_points=["Step-by-step method", "Temperature control", "Visual cues"],
                technique_focus="Classical French method"),
        Chapter(title="Common mistakes & fixes", duration_minutes=4,
                key_points=["What can go wrong", "How to recover", "Chef tips"],
                technique_focus="Troubleshooting"),
        Chapter(title="Plating & variations", duration_minutes=3,
                key_points=["Professional plating", "Seasonal variations", "Pairing suggestions"],
                technique_focus="Présentation"),
        Chapter(title="Recap & next steps", duration_minutes=2,
                key_points=["Key takeaways", "Practice challenge", "Next recipe teaser"],
                technique_focus="Consolidation"),
    ]


def _chapters_llm(idea: Dict, script_body: str) -> List[Chapter]:
    dish = idea.get("dish", idea.get("title", "French dish"))
    try:
        msg = _tracked_create(_CLIENT_FAST, "marcel/chapters",
            model=_MODEL_FAST,
            max_tokens=1024,
            system=(
                "You are Marcel, scriptwriter for a solo French cooking channel. "
                "Given a script body, generate a chapter outline for a long-form YouTube video (16–20 min total). "
                "Return ONLY a valid JSON array of 4–6 chapter objects. No markdown. No preamble.\n\n"
                "Each object: {\"title\": str, \"duration_minutes\": int, \"key_points\": [str, str, str], \"technique_focus\": str}"
            ),
            messages=[{"role": "user", "content": (
                f"Dish: {dish}\n\nScript excerpt (first 800 chars):\n{script_body[:800]}\n\n"
                "Generate a chapter outline for this long-form video."
            )}],
        )
        raw = msg.content[0].text.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
            raw = raw.strip()
        return [Chapter.model_validate(c) for c in json.loads(raw)]
    except Exception as e:
        _log.warning("Marcel chapters LLM failed: %s", e)
        return _chapters_stub(idea)


def _write_scripts_llm(idea: Dict, personal_prompts: Optional[Dict] = None) -> List[ScriptOut]:
    user_msg = f"Write scripts for this dish: {idea.get('dish', 'a French dish')}. Creative spin: {idea.get('creative_spin', '')}."

    messages = [{"role": "user", "content": user_msg}]
    msg = _tracked_create(_CLIENT, "marcel/write_scripts",
        model=_MODEL,
        max_tokens=4096,
        system=_SYSTEM_PROMPT,
        messages=messages,
    )
    raw = msg.content[0].text

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        messages = messages + [
            {"role": "assistant", "content": raw},
            {"role": "user", "content": "Your previous response was not valid JSON. Return only the JSON object, nothing else."},
        ]
        msg2 = _tracked_create(_CLIENT, "marcel/write_scripts_retry",
            model=_MODEL,
            max_tokens=4096,
            system=_SYSTEM_PROMPT,
            messages=messages,
        )
        data = json.loads(msg2.content[0].text)

    results = []
    for variant_key in ("TUTORIAL", "PERSONAL"):
        v = data[variant_key]
        results.append(ScriptOut(
            variant=variant_key,
            body=v["body"],
            hook_options=v.get("hook_options", []),
            verification=v.get("verification"),
        ))
    return results


def write_scripts(idea: Dict, stream: str = "SHORT", personal_prompts: Optional[Dict] = None) -> List[ScriptOut]:
    if not _LLM_AVAILABLE:
        scripts = _stub_impl(idea, personal_prompts)
    else:
        try:
            scripts = _write_scripts_llm(idea, personal_prompts)
        except Exception as e:
            _log.warning("LLM call failed, falling back to stub: %s", e)
            scripts = _stub_impl(idea, personal_prompts)

    # Generate chapter outline for long-form videos
    if stream == "LONG":
        chapters = _generate_chapters(idea, scripts)
        # Attach chapters to the TUTORIAL variant only
        scripts = [
            ScriptOut(**{**s.model_dump(), "chapters": chapters}) if s.variant == "TUTORIAL" else s
            for s in scripts
        ]
    return scripts
