# services/shared/llm_tracker.py
from __future__ import annotations
import logging
import time
from decimal import Decimal
from typing import Any

_log = logging.getLogger(__name__)

# Per-model pricing: (input_per_million_usd, output_per_million_usd)
_MODEL_RATES: dict[str, tuple[float, float]] = {
    "claude-haiku-4-5-20251001":  (0.80,  4.00),
    "claude-sonnet-4-6":          (3.00, 15.00),
    "claude-sonnet-4-6-20251101": (3.00, 15.00),
}
_DEFAULT_RATES = (3.00, 15.00)


def compute_cost(model: str, input_tokens: int, output_tokens: int) -> Decimal:
    """Return cost in USD as Decimal with 8-decimal precision."""
    in_rate, out_rate = _MODEL_RATES.get(model, _DEFAULT_RATES)
    cost = (input_tokens * in_rate + output_tokens * out_rate) / 1_000_000
    return Decimal(str(round(cost, 8)))


def tracked_create(client: Any, agent: str, **kwargs: Any) -> Any:
    """
    Drop-in replacement for client.messages.create(**kwargs).
    Captures token usage, computes cost, persists to llm_calls table.
    Never raises due to instrumentation failure — always returns the LLM response.
    """
    model: str = kwargs.get("model", "unknown")
    t0 = time.perf_counter()
    succeeded = False
    response = None

    try:
        response = client.messages.create(**kwargs)
        succeeded = True
        return response
    except Exception:
        raise
    finally:
        duration_ms = int((time.perf_counter() - t0) * 1000)

        input_tokens = 0
        output_tokens = 0
        if response is not None and hasattr(response, "usage") and response.usage is not None:
            input_tokens = getattr(response.usage, "input_tokens", 0) or 0
            output_tokens = getattr(response.usage, "output_tokens", 0) or 0

        cost = compute_cost(model, input_tokens, output_tokens)

        try:
            from services.shared.repo import record_llm_call
            record_llm_call(
                agent=agent,
                model=model,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cost_usd=float(cost),
                duration_ms=duration_ms,
                succeeded=succeeded,
            )
        except Exception as db_err:
            _log.warning("llm_tracker: DB write failed (non-fatal): %s", db_err)
