from typing import Dict, List, Optional
from pydantic import BaseModel

class ShootCard(BaseModel):
    camera: Dict
    lighting: Dict
    audio: Dict
    shotlist: List[Dict]
    props: List[str]

def make_shoot_card(script_body: str, gear: Optional[Dict] = None, time_of_day: str = "afternoon") -> ShootCard:
    """Minimal, import-safe stub."""
    gear = gear or {"camera": "iPhone 11", "mic": "phone mic or simple lav", "lights": "ring light"}
    wb_map = {"morning": "5200K", "afternoon": "5500K", "evening": "4500K"}
    wb = wb_map.get(time_of_day, "5500K")
    return ShootCard(
        camera={"device": gear["camera"], "fps": 30, "shutter": "1/60", "wb": wb, "resolution": "4K→1080x1920"},
        lighting={"key": "45° side of pan", "fill": "white board bounce", "notes": "avoid mixed window+ring"},
        audio={"mic": gear["mic"], "target_peak": "-12 dB", "tips": ["record 10s room tone"]},
        shotlist=[
            {"name": "hook", "angle": "overhead", "duration_s": 3},
            {"name": "prep", "angle": "45°", "duration_s": 8},
            {"name": "cook", "angle": "stovetop 45°", "duration_s": 20},
            {"name": "plate", "angle": "macro", "duration_s": 8},
            {"name": "cta", "angle": "face cam", "duration_s": 4},
        ],
        props=["chives", "white bounce", "garnish spoon"],
    )
