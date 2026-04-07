# services/agents/camille/main.py
import re, json, logging
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

PROP_CATALOG: Dict[str, List[str]] = {
    "beurre":      ["unsalted butter block", "light-coloured pan for colour visibility"],
    "omelette":    ["carbon steel omelette pan 20cm", "fork", "white plate"],
    "galette":     ["rolling pin", "parchment paper", "bench scraper"],
    "sauce":       ["fine mesh sieve", "small saucepan", "wooden spoon"],
    "vinaigrette": ["small bowl", "balloon whisk", "measuring spoons"],
    "confit":      ["dutch oven or deep saucepan", "candy thermometer"],
    "souffle":     ["ramekins", "electric mixer", "parchment collar"],
    "tarte":       ["tart tin with removable base", "rolling pin", "baking weights"],
    "creme":       ["double boiler or bain-marie", "instant-read thermometer"],
    "knife":       ["light maple cutting board", "chef knife"],
    "overhead":    ["overhead rig or stable book stack", "clean countertop"],
    "macro":       ["clip-on macro lens optional", "tweezers for garnish"],
    "lardons":     ["lardons or thick-cut bacon", "slotted spoon"],
    "poisson":     ["fish spatula", "stainless steel pan"],
    "viande":      ["meat thermometer", "cast iron pan or grill pan"],
}

ANGLE_MAP: Dict[str, Optional[str]] = {
    "overhead": "overhead",
    "close-up": "macro",
    "45":       "45deg",
    "stovetop": "stovetop 45deg",
    "face cam": "face cam",
}


class AngleSpec(BaseModel):
    label: str              # e.g. "overhead", "front-3/4", "close-up"
    position: str           # camera physical position description
    lens: str               # recommended focal length / lens type
    notes: str              # what to capture from this angle


class ShootCard(BaseModel):
    camera: Dict
    lighting: Dict
    audio: Dict
    shotlist: List[Dict]
    props: List[str]
    angles: List[AngleSpec] = []   # multi-angle specs; 3 standard angles minimum


def _default_angles() -> List[AngleSpec]:
    return [
        AngleSpec(label="overhead", position="Directly above work surface, 80–90 cm",
                  lens="35mm equivalent", notes="Top-down process and plating shots"),
        AngleSpec(label="front-3/4", position="Counter height, 45° offset",
                  lens="50mm equivalent", notes="Primary cooking — hands and pan visible"),
        AngleSpec(label="close-up", position="10–20 cm from subject",
                  lens="85mm equivalent", notes="Texture: browning, colour change, emulsification"),
    ]


def _stub_impl(
    script_body: str,
    gear: Dict,
    wb: str,
    catalog_props: List[str],
    shotlist: List[Dict],
) -> ShootCard:
    """Build a ShootCard without calling the LLM."""
    props = catalog_props if catalog_props else ["chives", "white bounce", "garnish spoon"]

    angles = [
        AngleSpec(
            label="overhead",
            position="Directly above the work surface, 80–90 cm height",
            lens="35mm equivalent, slight crop",
            notes="Capture mise en place, plating, and top-down process shots",
        ),
        AngleSpec(
            label="front-3/4",
            position="Front-facing, 45° offset, camera at counter height",
            lens="50mm equivalent",
            notes="Primary cooking shots — shows chef hands and pan simultaneously",
        ),
        AngleSpec(
            label="close-up",
            position="10–20 cm from subject, same side as dominant hand",
            lens="Macro or 85mm equivalent",
            notes="Texture details: browning, emulsification, colour change",
        ),
    ]

    return ShootCard(
        camera={"device": gear["camera"], "fps": 30, "shutter": "1/60", "wb": wb, "resolution": "4K→1080x1920"},
        lighting={"key": "45° side of pan", "fill": "white board bounce", "notes": "avoid mixed window+ring"},
        audio={"mic": gear["mic"], "target_peak": "-12 dB", "tips": ["record 10s room tone"]},
        shotlist=shotlist,
        props=props,
        angles=angles,
    )


def make_shoot_card(script_body: str, gear: Optional[Dict] = None, time_of_day: str = "afternoon") -> ShootCard:
    gear = gear or {"camera": "iPhone 11", "mic": "phone mic or simple lav", "lights": "ring light"}
    wb = {"morning": "5200K", "afternoon": "5500K", "evening": "4500K"}.get(time_of_day, "5500K")

    # 1. Catalog props from script body
    body_lower = script_body.lower()
    catalog_props: List[str] = []
    for key, values in PROP_CATALOG.items():
        if key in body_lower:
            catalog_props.extend(values)

    # 2. Extract stage directions
    directions = re.findall(r"\[([^\]]+)\]", script_body)

    # 3. Build shotlist from directions using ANGLE_MAP
    if directions:
        shotlist = []
        for direction in directions:
            direction_lower = direction.lower()
            matched_angle = None
            for key, angle in ANGLE_MAP.items():
                if key in direction_lower and angle is not None:
                    matched_angle = angle
                    break
            if matched_angle:
                shotlist.append({"name": direction[:40], "angle": matched_angle, "duration_s": 8})
        if not shotlist:
            shotlist = [
                {"name": "hook", "angle": "overhead", "duration_s": 3},
                {"name": "prep", "angle": "45°", "duration_s": 8},
                {"name": "cook", "angle": "stovetop 45°", "duration_s": 20},
                {"name": "plate", "angle": "macro", "duration_s": 8},
                {"name": "cta", "angle": "face cam", "duration_s": 4},
            ]
    else:
        shotlist = [
            {"name": "hook", "angle": "overhead", "duration_s": 3},
            {"name": "prep", "angle": "45°", "duration_s": 8},
            {"name": "cook", "angle": "stovetop 45°", "duration_s": 20},
            {"name": "plate", "angle": "macro", "duration_s": 8},
            {"name": "cta", "angle": "face cam", "duration_s": 4},
        ]

    # 4. LLM prop enrichment (and optional angles extraction)
    llm_props: List[str] = []
    llm_angles: List[AngleSpec] = []
    if _LLM_AVAILABLE:
        try:
            msg = _CLIENT.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=768,
                system=(
                    "You are a film production assistant. "
                    "Return ONLY valid JSON with two keys: "
                    "\"props\" (array of strings) and "
                    "\"angles\" (array of objects with keys label, position, lens, notes). "
                    "No explanation, no markdown."
                ),
                messages=[{
                    "role": "user",
                    "content": (
                        f"Script:\n{script_body}\n\n"
                        "List every physical prop and piece of equipment mentioned or implied in \"props\". "
                        "In \"angles\", provide at least 3 camera angle specs suited to this recipe."
                    ),
                }],
            )
            raw = json.loads(msg.content[0].text)
            llm_props = raw.get("props", [])
            raw_angles = raw.get("angles", [])
            for a in raw_angles:
                try:
                    llm_angles.append(AngleSpec(**a))
                except Exception:
                    pass
        except Exception as e:
            _log.warning("LLM prop/angle enrichment failed: %s", e)

    # 5. Deduplicate props
    all_props = catalog_props + llm_props
    seen = set()
    props: List[str] = []
    for p in all_props:
        if p.lower() not in seen:
            seen.add(p.lower())
            props.append(p)

    if not props:
        props = ["chives", "white bounce", "garnish spoon"]

    card = ShootCard(
        camera={"device": gear["camera"], "fps": 30, "shutter": "1/60", "wb": wb, "resolution": "4K→1080x1920"},
        lighting={"key": "45° side of pan", "fill": "white board bounce", "notes": "avoid mixed window+ring"},
        audio={"mic": gear["mic"], "target_peak": "-12 dB", "tips": ["record 10s room tone"]},
        shotlist=shotlist,
        props=props,
        angles=llm_angles,
    )

    # Ensure at least 3 standard angles are always present
    if len(card.angles) < 3:
        card = ShootCard(**{**card.model_dump(), "angles": _default_angles()})
    return card
