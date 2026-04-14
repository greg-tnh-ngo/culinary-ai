# services/shared/llm_client.py
"""
Plug-and-play LLM client factory.

Usage in agents:
    from services.shared.llm_client import get_llm
    _CLIENT, _MODEL = get_llm("julien")
    _CLIENT_FAST, _MODEL_FAST = get_llm("marcel", tier="fast")

Config lives in services/shared/agent_models.toml.
Changing backend/model there takes effect on next process start — no code changes needed.
"""
from __future__ import annotations

import logging
import tomllib
from pathlib import Path
from typing import Any, Tuple

_log = logging.getLogger(__name__)
_CONFIG_PATH = Path(__file__).parent / "agent_models.toml"


def _load_config() -> dict:
    with open(_CONFIG_PATH, "rb") as f:
        return tomllib.load(f)


_config = _load_config()


# ── Ollama adapter ─────────────────────────────────────────────────────────────

class _OllamaResponse:
    """Mimics anthropic.types.Message so .content[0].text and .usage work unchanged."""

    def __init__(self, openai_resp: Any) -> None:
        text = openai_resp.choices[0].message.content or ""
        self.content = [type("Block", (), {"text": text})()]
        usage = openai_resp.usage
        self.usage = type("Usage", (), {
            "input_tokens": getattr(usage, "prompt_tokens", 0),
            "output_tokens": getattr(usage, "completion_tokens", 0),
        })()
        self.model = openai_resp.model


class _OllamaMessages:
    def __init__(self, openai_client: Any, default_model: str) -> None:
        self._client = openai_client
        self._default_model = default_model

    def create(
        self,
        *,
        model: str | None = None,
        max_tokens: int = 2048,
        system: str | None = None,
        messages: list | None = None,
        **_: Any,
    ) -> _OllamaResponse:
        msgs: list[dict] = []
        if system:
            msgs.append({"role": "system", "content": system})
        msgs.extend(messages or [])

        resp = self._client.chat.completions.create(
            model=model or self._default_model,
            messages=msgs,
            max_tokens=max_tokens,
        )
        return _OllamaResponse(resp)


class OllamaClient:
    """Drop-in replacement for anthropic.Anthropic() that routes to a local Ollama instance."""

    def __init__(self, base_url: str, model: str) -> None:
        from openai import OpenAI
        self.messages = _OllamaMessages(
            OpenAI(base_url=base_url, api_key="ollama"),
            model,
        )


# ── Factory ────────────────────────────────────────────────────────────────────

def get_llm(agent: str, tier: str = "primary") -> Tuple[Any, str]:
    """
    Return (client, model_name) for the given agent and tier.

    tier="primary"  — the main (heavier) LLM call for this agent
    tier="fast"     — the lighter call (e.g. haiku-tier); falls back to primary
                      if not separately configured

    Active profile is read from agent_models.toml → active_profile.
    Switch profiles by changing that one line and restarting the API.

    The returned client exposes .messages.create(**kwargs) compatible with
    the Anthropic SDK signature used throughout this codebase.
    """
    profile: str = _config.get("active_profile", "anthropic")
    agents_cfg: dict = _config.get("profiles", {}).get(profile, {}).get("agents", {})
    agent_cfg: dict = agents_cfg.get(agent, {})

    # Resolve tier: use fast sub-table if requested and present, else primary
    if tier != "primary" and tier in agent_cfg and isinstance(agent_cfg[tier], dict):
        tier_cfg = agent_cfg[tier]
    else:
        # Primary config: exclude sub-table keys (they are dicts, not strings)
        tier_cfg = {k: v for k, v in agent_cfg.items() if not isinstance(v, dict)}

    defaults = _config.get("defaults", {})
    backend: str = tier_cfg.get("backend", "anthropic")
    model: str = tier_cfg.get("model", "claude-haiku-4-5-20251001")

    if backend == "ollama":
        base_url: str = tier_cfg.get("ollama_base_url") or defaults.get(
            "ollama_base_url", "http://localhost:11434/v1"
        )
        return OllamaClient(base_url=base_url, model=model), model

    if backend == "groq":
        try:
            from openai import OpenAI
            from services.shared.db import _cfg as _db_cfg
            api_key = _db_cfg.GROQ_API_KEY
            if not api_key:
                raise ValueError("GROQ_API_KEY not set in .env")
            client = OpenAI(base_url="https://api.groq.com/openai/v1", api_key=api_key)
            # Reuse OllamaClient's adapter — same OpenAI-compatible interface
            groq_client = object.__new__(OllamaClient)
            groq_client.messages = _OllamaMessages(client, model)
            return groq_client, model
        except Exception as exc:
            _log.warning("get_llm(%s, %s): groq init failed — %s", agent, tier, exc)
            return None, model

    # anthropic backend
    try:
        import anthropic
        from services.shared.db import _cfg as _db_cfg
        api_key = _db_cfg.ANTHROPIC_API_KEY
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY not set in .env")
        return anthropic.Anthropic(api_key=api_key), model
    except Exception as exc:
        _log.warning("get_llm(%s, %s): anthropic init failed — %s", agent, tier, exc)
        return None, model
