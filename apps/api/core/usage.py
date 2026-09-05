"""Token usage → trace, for every chat-model call made through settings.get_model().

Each call writes one ``llm.usage`` trace row: model, prompt / cached / cache-write / completion
/ reasoning tokens, an estimated USD cost (prices from settings, per 1M tokens) and the caller
(``kind``: the ``llm.*`` tag we put on our own structured calls, or the LangGraph node /
deep-agent name for agent loops). ``summarize()`` aggregates rows for reports.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from langchain_core.callbacks import BaseCallbackHandler


def estimate_cost_usd(
    prompt: int, cached: int, cache_write: int, completion: int, prices: dict[str, float]
) -> float:
    """prices: USD per 1M tokens — input, cached_input, cache_write, output.
    Cached tokens are billed at the cache-read price, freshly written ones at the cache-write
    price, the rest of the prompt at the input price."""
    fresh = max(prompt - cached - cache_write, 0)
    return (
        fresh * prices["input"]
        + cached * prices["cached_input"]
        + cache_write * prices["cache_write"]
        + completion * prices["output"]
    ) / 1_000_000


class UsageTrace(BaseCallbackHandler):
    """Attach to a chat model: ``ChatOpenAI(..., callbacks=[UsageTrace(model, prices)])``."""

    raise_error = False

    def __init__(self, model: str, prices: dict[str, float]) -> None:
        self.model = model
        self.prices = prices
        self._kind: dict[UUID, str] = {}

    def on_chat_model_start(
        self,
        serialized: dict[str, Any],
        messages: Any,
        *,
        run_id: UUID,
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> None:
        kind = next((t for t in (tags or []) if t.startswith("llm.")), None)
        if kind is None:
            md = metadata or {}
            kind = f"agent:{md.get('lc_agent_name') or md.get('langgraph_node') or 'unknown'}"
        self._kind[run_id] = kind

    def on_llm_end(self, response: Any, *, run_id: UUID, **kwargs: Any) -> None:
        from core.trace import trace

        usage = (response.llm_output or {}).get("token_usage") or {}
        if not usage:
            try:
                # Responses API (use_responses_api=True) leaves llm_output empty; LangChain's
                # normalized usage_metadata carries cache read/creation and reasoning tokens.
                um = response.generations[0][0].message.usage_metadata or {}
                itd = um.get("input_token_details") or {}
                otd = um.get("output_token_details") or {}
                usage = {
                    "prompt_tokens": um.get("input_tokens", 0),
                    "completion_tokens": um.get("output_tokens", 0),
                    "prompt_tokens_details": {
                        "cached_tokens": itd.get("cache_read", 0),
                        "cache_write_tokens": itd.get("cache_creation", 0),
                    },
                    "completion_tokens_details": {"reasoning_tokens": otd.get("reasoning", 0)},
                }
            except Exception:  # noqa: BLE001
                return
        ptd = usage.get("prompt_tokens_details") or {}
        ctd = usage.get("completion_tokens_details") or {}
        prompt = int(usage.get("prompt_tokens") or 0)
        cached = int(ptd.get("cached_tokens") or 0)
        cache_write = int(ptd.get("cache_write_tokens") or 0)
        completion = int(usage.get("completion_tokens") or 0)
        trace(
            "llm.usage",
            model=self.model,
            caller=self._kind.pop(run_id, "unknown"),
            prompt_tokens=prompt,
            cached_tokens=cached,
            cache_write_tokens=cache_write,
            completion_tokens=completion,
            reasoning_tokens=int(ctd.get("reasoning_tokens") or 0),
            cost_usd=round(
                estimate_cost_usd(prompt, cached, cache_write, completion, self.prices), 6
            ),
        )


def summarize(rows: list[dict[str, Any]]) -> dict[str, dict[str, float]]:
    """Per kind (and 'all'): calls, avg prompt/cached/completion tokens, cache-hit ratio, avg and
    total cost."""
    out: dict[str, dict[str, float]] = {}
    groups: dict[str, list[dict[str, Any]]] = {"all": []}
    for r in rows:
        if r.get("kind") != "llm.usage":
            continue
        groups["all"].append(r)
        groups.setdefault(str(r.get("caller", "unknown")), []).append(r)
    for name, rs in groups.items():
        if not rs:
            continue
        n = len(rs)
        p = sum(int(x.get("prompt_tokens", 0)) for x in rs)
        c = sum(int(x.get("cached_tokens", 0)) for x in rs)
        o = sum(int(x.get("completion_tokens", 0)) for x in rs)
        cost = sum(float(x.get("cost_usd", 0)) for x in rs)
        out[name] = {
            "calls": n,
            "avg_prompt": p / n,
            "avg_cached": c / n,
            "avg_completion": o / n,
            "cache_hit_ratio": (c / p) if p else 0.0,
            "avg_cost_usd": cost / n,
            "total_cost_usd": cost,
        }
    return out
