"""settings.get_model() pins the model; usage/cost tracing; the cached record prefix is stable."""

from __future__ import annotations

import os
from uuid import uuid4

from core.settings import Settings
from core.usage import UsageTrace, estimate_cost_usd, summarize


def test_get_model_pins_gpt_5_with_reasoning_none_and_temperature_zero():
    s = Settings(MODEL_PROVIDER="openai", OPENAI_API_KEY="sk-test", MODEL_PINNED="gpt-5.6-luna")
    m = s.get_model()
    assert m.model_name == "gpt-5.6-luna" and m.temperature == 0
    assert m.reasoning_effort == "none"
    assert any(isinstance(cb, UsageTrace) for cb in (m.callbacks or []))


def test_get_model_keeps_gpt_4_without_reasoning_param():
    s = Settings(
        MODEL_PROVIDER="openai", OPENAI_API_KEY="sk-test", MODEL_PINNED="gpt-4.1-2025-04-14"
    )
    m = s.get_model()
    assert m.model_name == "gpt-4.1-2025-04-14" and m.reasoning_effort is None


def test_cost_estimate_uses_cache_prices():
    prices = {"input": 0.20, "cached_input": 0.02, "cache_write": 0.25, "output": 1.20}
    # 2300 prompt of which 2283 cached, 14 written, 3 fresh; 20 output
    cost = estimate_cost_usd(2300, 2283, 14, 20, prices)
    expected = (3 * 0.20 + 2283 * 0.02 + 14 * 0.25 + 20 * 1.20) / 1e6
    assert abs(cost - expected) < 1e-12


def test_usage_callback_writes_trace_row(records_root):
    from core import trace as tr

    class _Resp:
        llm_output = {
            "token_usage": {
                "prompt_tokens": 1500,
                "completion_tokens": 30,
                "prompt_tokens_details": {"cached_tokens": 1200, "cache_write_tokens": 0},
                "completion_tokens_details": {"reasoning_tokens": 0},
            }
        }

    cb = UsageTrace("gpt-5.6-luna", Settings().prices)
    rid = uuid4()
    cb.on_chat_model_start({}, [], run_id=rid, tags=["llm.next_question"], metadata={})
    cb.on_llm_end(_Resp(), run_id=rid)
    rows = tr.recent("llm.usage")
    assert rows and rows[-1]["caller"] == "llm.next_question"
    assert rows[-1]["cached_tokens"] == 1200 and rows[-1]["cost_usd"] > 0
    s = summarize(rows[-1:])
    assert s["all"]["calls"] == 1 and s["llm.next_question"]["cache_hit_ratio"] == 0.8


def test_record_prefix_is_stable_within_a_day(records_root):
    from core.llm import record_prefix
    from record.store import get_store

    store = get_store()
    p, b = store.load_profile("P001"), store.load_baseline("P001")
    a = record_prefix(p, b)
    assert a == record_prefix(p, b)
    assert "王伯" in a and "基線（平常）" in a and "timeline（近 14 天" in a
    assert os.environ.get("MODEL_PROVIDER") == "mock"
