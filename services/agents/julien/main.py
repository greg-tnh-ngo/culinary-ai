from pydantic import BaseModel
from typing import Literal, List

class IdeaCard(BaseModel):
    dish: str
    stream: Literal["SHORT","LONG","SHORT+LONG"]
    creative_spin: str
    production_difficulty: int  # 0..5
    culinary_complexity: int    # 0..5
    estimated_cost: float
    seasonality: str | None
    inspiration: List[dict]
    hooks: List[str]
    cta: List[str]

def curate_stub() -> IdeaCard:
    return IdeaCard(
        dish="Omelette aux fines herbes",
        stream="SHORT",
        creative_spin="3-technique omelette: classic fold + chives oil finish",
        production_difficulty=1,
        culinary_complexity=2,
        estimated_cost=3.50,
        seasonality="spring",
        inspiration=[{"url":"https://example.com/omelette", "quoted":"Classic French technique with chives."}],
        hooks=[
            "The 10-second French omelette test",
            "Your pan is too hot — fix it like this"
        ],
        cta=["Save for breakfast tomorrow", "Try with fines herbes tonight"]
    )
