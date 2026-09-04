"""Test double for the Intake Agent's planner (pytest only; never used in production)."""

from __future__ import annotations

from record_schema import DIMENSION_LABELS

from core.llm import MockLLM, NextQuestionOut

LABEL_TO_KEY = {v["zh-TW"]: k for k, v in DIMENSION_LABELS.items()}
RED_FACTS = [
    "是怎麼跌的？",
    "哪裡痛？",
    "能不能自己站起來？",
    "現在清不清醒？",
    "有沒有流血？",
    "從什麼時候開始的？",
]


class ScriptedLLM(MockLLM):
    """Deterministic decisions shaped like the real model's structured output."""

    name = "scripted-test-double"

    def next_question(self, ctx):
        asked = ctx.get("asked") or []
        if ctx.get("budget", 0) <= 0:
            return NextQuestionOut(ask=False, reason="預算用完")
        if ctx.get("phase") == "red":
            for q in RED_FACTS:
                if not any(a.startswith(q) for a in asked):
                    return NextQuestionOut(
                        ask=True, dimension=None, question=q, reason="紅燈：護理師到場前的關鍵事實"
                    )
            return NextQuestionOut(ask=False, reason="關鍵事實已足夠")
        unknown = [LABEL_TO_KEY[lbl] for lbl in ctx.get("unknown") or [] if lbl in LABEL_TO_KEY]
        asked_dims = set()
        if not unknown:
            return NextQuestionOut(ask=False, reason="八維度已足夠")
        dim = next((d for d in unknown if d not in asked_dims), unknown[0])
        return NextQuestionOut(
            ask=True,
            dimension=dim,
            question=f"{DIMENSION_LABELS[dim]['zh-TW']}今天怎麼樣？",
            reason=f"{DIMENSION_LABELS[dim]['zh-TW']}還沒提到（test double）",
        )
