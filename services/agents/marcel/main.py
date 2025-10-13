# services/agents/marcel/main.py
from typing import Dict, List, Optional
from pydantic import BaseModel

class ScriptOut(BaseModel):
    variant: str
    body: str

def write_scripts(idea: Dict, personal_prompts: Optional[Dict] = None) -> List[ScriptOut]:
    """Minimal stub for debugging import issues."""
    dish = idea.get("dish", idea.get("title", "Plat français"))
    return [
        ScriptOut(variant="TUTORIAL", body=f"Today we cook {dish}. Steps: prep → heat → butter."),
        ScriptOut(variant="PERSONAL", body=f"[Your story about {dish}] Then show your key technique.")
    ]
