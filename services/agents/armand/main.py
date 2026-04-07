# services/agents/armand/main.py
import json, logging
from datetime import date, timedelta
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

try:
    from PIL import Image
    import pytesseract
    import io
    _OCR_AVAILABLE = True
except ImportError:
    _OCR_AVAILABLE = False


def _current_monday() -> date:
    today = date.today()
    return today - timedelta(days=today.weekday())


class RecipeCost(BaseModel):
    recipe_id: str
    recipe_title: str
    estimated_cost: float       # cost of missing ingredients only
    missing_ingredients: List[str]
    in_stock_ingredients: List[str]


class WeekPlan(BaseModel):
    week_id: str                # ISO date — Monday of the week
    recipes: List[RecipeCost]
    total_estimated_cost: float
    budget_limit: float
    budget_remaining: float
    over_budget: bool
    swap_suggestions: List[str] # LLM suggestions when over budget


class ReceiptItem(BaseModel):
    name: str
    qty: float
    unit: str
    unit_price: float
    total_price: float


class ReceiptResult(BaseModel):
    store: str
    items: List[ReceiptItem]
    total: float
    matched_ingredients: List[str]   # names matched to DB
    unmatched_items: List[str]       # not found in ingredient catalog


class GroceryItem(BaseModel):
    ingredient_id: str
    name: str
    category: Optional[str]
    unit: Optional[str]
    qty_needed: float
    in_stock: float
    to_buy: float
    unit_price: Optional[float]
    estimated_cost: float


class GroceryList(BaseModel):
    week_id: str
    recipe_titles: List[str]
    items: List[GroceryItem]   # only ingredients with to_buy > 0
    total_estimated_cost: float


class SwapSuggestion(BaseModel):
    original_ingredient: str
    swap_ingredient: str
    reason: str
    estimated_savings: float


# ── Week planning ─────────────────────────────────────────────────────────────

def plan_week(recipe_ids: List[str], week_id: Optional[date] = None) -> WeekPlan:
    from services.shared.repo import get_recipe_with_ingredients, get_or_create_ledger_week, update_ledger_planned
    if week_id is None:
        week_id = _current_monday()

    ledger = get_or_create_ledger_week(week_id)
    budget_limit = ledger["budget_limit"]

    recipe_costs: List[RecipeCost] = []
    total_cost = 0.0

    for recipe_id in recipe_ids:
        recipe = get_recipe_with_ingredients(recipe_id)
        if not recipe:
            continue
        missing = []
        in_stock = []
        cost = 0.0
        for ing in recipe["ingredients"]:
            qty_needed = ing["qty_needed"] or 0.0
            in_stock_qty = ing["current_qty"]
            if in_stock_qty >= qty_needed:
                in_stock.append(ing["name"])
            else:
                missing.append(ing["name"])
                # cost of the shortfall
                shortfall = qty_needed - in_stock_qty
                price = ing["avg_price_per_unit"] or 0.0
                cost += shortfall * price
        recipe_costs.append(RecipeCost(
            recipe_id=recipe_id,
            recipe_title=recipe["title"],
            estimated_cost=round(cost, 2),
            missing_ingredients=missing,
            in_stock_ingredients=in_stock,
        ))
        total_cost += cost

    total_cost = round(total_cost, 2)
    update_ledger_planned(week_id, total_cost, recipe_ids)

    over_budget = total_cost > budget_limit
    swaps: List[str] = []
    if over_budget and _LLM_AVAILABLE:
        swaps = _suggest_swaps_llm(recipe_costs, budget_limit, total_cost)

    return WeekPlan(
        week_id=week_id.isoformat(),
        recipes=recipe_costs,
        total_estimated_cost=total_cost,
        budget_limit=budget_limit,
        budget_remaining=round(budget_limit - total_cost, 2),
        over_budget=over_budget,
        swap_suggestions=swaps,
    )


def _suggest_swaps_llm(recipe_costs: List[RecipeCost], budget_limit: float, total_cost: float) -> List[str]:
    missing_all = []
    for rc in recipe_costs:
        missing_all.extend(rc.missing_ingredients)
    if not missing_all:
        return []
    try:
        msg = _CLIENT.messages.create(
            model="claude-sonnet-4-6-20251101",
            max_tokens=512,
            system=(
                "You are Armand, budget manager for a solo French cooking channel. "
                "Your sole job is to protect a $100/week ingredient budget without "
                "compromising classical French technique or video quality.\n\n"
                "RULES:\n"
                "- Swaps must preserve the core technique (e.g. if a recipe requires "
                "an emulsification agent, the swap must also emulsify).\n"
                "- Never suggest removing a hero ingredient (the dish's title ingredient).\n"
                "- Prefer swaps available at IGA, Maxi, or Metro (Montréal grocery chains).\n"
                "- Each suggestion must include the estimated saving in dollars.\n"
                "- Return ONLY a valid JSON array of objects. No markdown. No preamble.\n\n"
                "OUTPUT SCHEMA (strict):\n"
                '[{"original": str, "swap": str, "reason": str, "saving_cad": float}]'
            ),
            messages=[{"role": "user","content": (
                f"Weekly budget: ${budget_limit:.2f} CAD\n"
                f"Projected spend: ${total_cost:.2f} CAD\n"
                f"Overage to close: ${round(total_cost - budget_limit, 2):.2f} CAD\n\n"
                f"Recipes this week:\n"
                + "\n".join(
                    f"- {rc.recipe_title}: missing {', '.join(rc.missing_ingredients)} "
                    f"(est. ${rc.estimated_cost:.2f})"
                    for rc in recipe_costs
                )
                + "\n\nSuggest 2–3 swaps that close the overage. "
                "Prioritise swaps with the highest saving first. "
                "If no swap can close the gap alone, say so in the reason field.")}],
        )
        return json.loads(msg.content[0].text.strip())
    except Exception as e:
        _log.warning("Armand swap LLM failed: %s", e)
        return [f"Consider reducing portion sizes or substituting expensive items to save ${round(total_cost - budget_limit, 2):.2f}."]


# ── Grocery list ──────────────────────────────────────────────────────────────

def get_grocery_list(week_id: Optional[date] = None) -> GroceryList:
    from services.shared.repo import get_grocery_list as _repo_grocery
    if week_id is None:
        week_id = _current_monday()
    data = _repo_grocery(week_id)
    return GroceryList(
        week_id=week_id.isoformat(),
        recipe_titles=data.get("recipe_titles", []),
        items=[GroceryItem(**i) for i in data["items"]],
        total_estimated_cost=data.get("total_estimated_cost", 0.0),
    )


# ── Receipt ingestion ─────────────────────────────────────────────────────────

def ingest_receipt(image_bytes: bytes, store: str = "unknown") -> ReceiptResult:
    from services.shared.repo import (
        list_ingredients, get_ingredient_by_name, update_ingredient_qty,
        upsert_ingredient_price, save_purchase, update_ledger_actual,
    )

    # OCR
    raw_text = ""
    if _OCR_AVAILABLE:
        try:
            img = Image.open(io.BytesIO(image_bytes))
            raw_text = pytesseract.image_to_string(img)
        except Exception as e:
            _log.warning("OCR failed: %s", e)

    # LLM parse of OCR text (or manual entry fallback)
    items: List[ReceiptItem] = []
    if _LLM_AVAILABLE and raw_text:
        items = _parse_receipt_llm(raw_text)
    elif not raw_text:
        _log.warning("No OCR text extracted — receipt ingestion requires a clear image")

    # Match items to ingredient catalog
    existing = {i["name"].lower(): i for i in list_ingredients()}
    matched, unmatched = [], []
    total = sum(i.total_price for i in items)

    purchase_items = []
    for item in items:
        key = item.name.lower()
        matched_ing = existing.get(key)
        # fuzzy: check if any catalog name is a substring
        if not matched_ing:
            for cat_name, cat_ing in existing.items():
                if cat_name in key or key in cat_name:
                    matched_ing = cat_ing
                    break
        if matched_ing:
            matched.append(matched_ing["name"])
            update_ingredient_qty(matched_ing["id"], item.qty)
            if item.unit_price > 0:
                upsert_ingredient_price(matched_ing["id"], item.unit_price)
            purchase_items.append({
                "ingredient_id": matched_ing["id"],
                "name": item.name,
                "qty": item.qty,
                "unit": item.unit,
                "unit_price": item.unit_price,
            })
        else:
            unmatched.append(item.name)
            purchase_items.append({"name": item.name, "qty": item.qty, "unit": item.unit, "unit_price": item.unit_price})

    if purchase_items:
        from datetime import datetime, timezone
        save_purchase(datetime.now(timezone.utc), store, purchase_items, total)
        update_ledger_actual(_current_monday(), total)

    return ReceiptResult(
        store=store,
        items=items,
        total=round(total, 2),
        matched_ingredients=matched,
        unmatched_items=unmatched,
    )


def _parse_receipt_llm(raw_text: str) -> List[ReceiptItem]:
    try:
        msg = _CLIENT.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=1024,
            system=(
                "You are a receipt parser for a French cooking channel based in Montréal, Québec.\n\n"
                "INPUT: raw OCR text from a grocery receipt (may contain French, English, "
                "abbreviations, price formatting like '2,99' or '2.99', and OCR noise).\n\n"
                "RULES:\n"
                "- Normalise units to: g, kg, ml, l, pc (piece), bunch, pkg.\n"
                "- If qty and unit are ambiguous (e.g. '1 pkg chicken thighs'), set qty=1, unit='pkg'.\n"
                "- Ignore non-food line items: taxes (TPS/TVQ), subtotals, loyalty points, "
                "bag fees, receipt numbers.\n"
                "- Normalise prices: treat ',' as decimal separator if no '.' present.\n"
                "- If unit_price is not explicit, derive it as total_price / qty.\n"
                "- If a field cannot be determined, use 0.0 for floats, 'pc' for unit.\n"
                "- Return ONLY a valid JSON array. No markdown. No preamble. No trailing comma.\n\n"
                "OUTPUT SCHEMA (strict):\n"
                '[{"name": str, "qty": float, "unit": str, '
                '"unit_price": float, "total_price": float}]'
            ),
            messages=[{
                "role": "user",
                "content": (
                    f"Parse this receipt into structured line items.\n\n"
                    f"RECEIPT TEXT:\n{raw_text[:2000]}\n\n"
                    "Return only the food/ingredient line items as a JSON array."
                )
            }],
        )
        raw = msg.content[0].text.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
            raw = raw.strip()
        return [ReceiptItem.model_validate(i) for i in json.loads(raw)]
    except Exception as e:
        _log.warning("Receipt LLM parse failed: %s", e)
        return []
