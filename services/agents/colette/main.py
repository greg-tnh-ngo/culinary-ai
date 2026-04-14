# services/agents/colette/main.py
import json, logging
from typing import Dict, List, Optional
from pydantic import BaseModel
from services.shared.db import _cfg

_log = logging.getLogger(__name__)
try:
    from services.shared.llm_client import get_llm as _get_llm
    from services.shared.llm_tracker import tracked_create as _tracked_create
    _CLIENT, _MODEL = _get_llm("colette")
    _LLM_AVAILABLE = _CLIENT is not None
except Exception:
    _CLIENT, _MODEL, _LLM_AVAILABLE = None, "claude-sonnet-4-6", False
    _tracked_create = None


class QCResult(BaseModel):
    culinary_pass: bool
    style_pass: bool
    plagiarism_score: float   # 0.0–1.0; overall_pass blocked if > 0.7
    issues: List[str]
    overall_pass: bool        # culinary_pass AND style_pass AND plagiarism_score <= 0.7


class PlatformAsset(BaseModel):
    platform: str             # "youtube", "tiktok", "instagram"
    title: str
    description: str
    hashtags: List[str]
    cover_concept: str        # text description of thumbnail concept


class ReleasePacket(BaseModel):
    video_id: str
    qc: QCResult
    assets: List[PlatformAsset]
    approved: bool = False
    notes: str = ""


def _stub_impl(video_id: str) -> ReleasePacket:
    # Stub always fails QC — a silent pass would let unreviewed scripts through
    qc = QCResult(
        culinary_pass=False,
        style_pass=False,
        plagiarism_score=0.0,
        issues=["QC unavailable: LLM could not be reached. Re-run when the API key is set and the service is reachable."],
        overall_pass=False,
    )
    return ReleasePacket(video_id=video_id, qc=qc, assets=[])


_QC_SYSTEM = (
    "You are Colette, the quality controller for a solo French cooking channel. "
    "Given a script with verification data and a shoot card, perform two checks:\n\n"
    "CULINARY CHECK: verify that temperatures, ratios, and technique claims in the verification JSON are accurate. "
    "Flag any that are outside safe or standard culinary ranges.\n\n"
    "STYLE CHECK: verify the script follows these brand rules — "
    "no words: guys, y'all, amazing; "
    "sentences under 15 words; "
    "French technique named first then English translation; "
    "viewer addressed as 'you' directly.\n\n"
    "PLAGIARISM: estimate a similarity score 0.0–1.0 based on how closely the script echoes known published recipes without attribution.\n\n"
    "Return ONLY a valid JSON object — no markdown, no explanation — with these exact fields: "
    "culinary_pass (bool), style_pass (bool), plagiarism_score (float), issues (array of strings), "
    "overall_pass (bool — true only if culinary_pass AND style_pass AND plagiarism_score <= 0.7)."
)

_ASSETS_SYSTEM = (
    "You are Colette, writing YouTube metadata for a solo French cooking channel. "
    "Brand rules: no 'guys', 'y'all', 'amazing'; address viewer as 'you'; titles under 70 characters; "
    "descriptions 2–3 sentences, technique-first; 5 hashtags per asset. "
    "Return ONLY a valid JSON array of 3 objects — no markdown, no explanation. "
    "Each object has: platform (always 'youtube'), title (string), description (string), "
    "hashtags (array of 5 strings with # prefix), cover_concept (string describing thumbnail visually)."
)


def _make_release_packet_llm(
    video_id: str,
    scripts: List[Dict],
    edit_directive: Dict,
    shoot_card: Dict,
) -> ReleasePacket:
    tutorial = next((s for s in scripts if s.get("variant") == "TUTORIAL"), scripts[0] if scripts else {})
    verification = tutorial.get("verification") or {}
    body = tutorial.get("body", "")

    # Step 1: QC
    qc_user = (
        f"Script body:\n{body}\n\n"
        f"Verification data:\n{json.dumps(verification)}\n\n"
        f"Shoot card props: {json.dumps(shoot_card.get('props', []))}"
    )
    qc_msg = _tracked_create(_CLIENT, "colette/qc",
        model=_MODEL,
        max_tokens=2048,
        system=_QC_SYSTEM,
        messages=[{"role": "user", "content": qc_user}],
    )
    qc_raw = qc_msg.content[0].text.strip()
    if qc_raw.startswith("```"):
        qc_raw = qc_raw.split("```")[1]
        if qc_raw.startswith("json"):
            qc_raw = qc_raw[4:]
        qc_raw = qc_raw.strip()
    qc = QCResult.model_validate(json.loads(qc_raw))

    # Step 2: generate assets only if QC passed
    assets: List[PlatformAsset] = []
    if qc.overall_pass:
        assets_msg = _tracked_create(_CLIENT, "colette/assets",
            model=_MODEL,
            max_tokens=2048,
            system=_ASSETS_SYSTEM,
            messages=[{"role": "user", "content": f"Script:\n{body[:1200]}"}],
        )
        assets_raw = assets_msg.content[0].text.strip()
        if assets_raw.startswith("```"):
            assets_raw = assets_raw.split("```")[1]
            if assets_raw.startswith("json"):
                assets_raw = assets_raw[4:]
            assets_raw = assets_raw.strip()
        assets = [PlatformAsset.model_validate(a) for a in json.loads(assets_raw)]

    return ReleasePacket(video_id=video_id, qc=qc, assets=assets)


def make_release_packet(
    video_id: str,
    scripts: List[Dict],
    edit_directive: Dict,
    shoot_card: Dict,
) -> ReleasePacket:
    if not _LLM_AVAILABLE:
        return _stub_impl(video_id)
    try:
        return _make_release_packet_llm(video_id, scripts, edit_directive, shoot_card)
    except Exception as e:
        _log.warning("Colette LLM failed (%s: %s), falling back to stub", type(e).__name__, e)
        return _stub_impl(video_id)
