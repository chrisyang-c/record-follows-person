"""Multi-turn intake dialog (照護者聊天式引導).

Rule-based turn planner on top of the extractor: after the caregiver's first sentence, ask one
question at a time about what the eight dimensions still lack (dimensions already mentioned
are never asked), 2–4 quick replies per question, always 「不知道」, at most MAX_TURNS
follow-ups. A red-flag fact ends the dialog immediately (the nurse is notified; no summary
confirmation — ARCHITECTURE §11).

The planner is deterministic; only the per-utterance extraction uses the model (or the
lexicon in mock mode). Everything stays in the caregiver's own words.
"""

from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel, Field
from record_schema import (
    DIMENSIONS,
    Baseline,
    DimensionValue,
    FollowupQA,
    Profile,
    Provenance,
    RedFlagResult,
    StructuredObservation,
)

from core.llm import get_llm
from red_flags.rules import RedFlagInput, evaluate, render_lines

MAX_TURNS = 4
UNKNOWN = "不知道"
ASK_ORDER = ["intake", "sleep", "cognition", "function", "pain", "vitals", "elimination", "skin"]

# (question, quick replies) — everyday words; every reply parses on its own.
QUESTIONS: dict[str, tuple[str, list[str]]] = {
    "intake": ("{name}今天吃得怎樣？", ["吃完", "吃一半", "幾乎沒吃", UNKNOWN]),
    "sleep": ("昨晚睡得怎樣？", ["睡得好", "晚上起來一兩次", "晚上起來三次以上", UNKNOWN]),
    "cognition": ("精神、講話跟平常一樣嗎？", ["精神跟平常一樣", "反應變慢", "講話變少", UNKNOWN]),
    "function": (
        "走路、站起來跟平常比呢？",
        ["走路跟平常一樣", "走路比較慢", "走路要人扶", UNKNOWN],
    ),
    "pain": ("有沒有哪裡痛？", ["沒有痛", "有點痛", "很痛", UNKNOWN]),
    "vitals": ("有咳嗽、喘，或摸起來燙嗎？", ["都沒有", "有咳嗽", "摸起來燙", UNKNOWN]),
    "elimination": ("大小便有什麼不一樣嗎？", ["大便正常", "沒大便", "拉肚子", UNKNOWN]),
    "skin": ("皮膚有沒有紅或破皮？", ["皮膚沒事", "皮膚有紅", "有破皮", UNKNOWN]),
}
EVENT_QUESTIONS: dict[str, tuple[str, list[str]]] = {
    "fall": ("有撞到頭嗎？能自己站起來嗎？", ["頭沒有撞到", "撞到頭", "站不起來", UNKNOWN]),
    "medication_issue": (
        "藥是不肯吃，還是吐出來了？",
        ["不肯吃藥", "把藥吐出來", "漏吃一次", UNKNOWN],
    ),
    "choking": (
        "是喝水還是吃東西嗆到？現在還在咳嗎？",
        ["喝水嗆到", "吃東西嗆到", "現在還在咳", UNKNOWN],
    ),
    "behavior": (
        "是想出去、動手，還是一直走來走去？",
        ["一直想跑出去", "動手打人", "一直走來走去", UNKNOWN],
    ),
    "seems_different": ("哪裡跟平常不一樣？", ["吃得比較少", "比較安靜不講話", "一直睡", UNKNOWN]),
}
# replies that mean「跟平常一樣」for the asked dimension
NORMAL_REPLIES = {
    "睡得好",
    "精神跟平常一樣",
    "走路跟平常一樣",
    "沒有痛",
    "都沒有",
    "大便正常",
    "皮膚沒事",
    "跟平常一樣",
    "正常",
    "沒有",
}


class Turn(BaseModel):
    text: str
    dimension: str | None = None  # "intake"… or "event:fall" … or None for free text
    quick: bool = False


class NextQuestion(BaseModel):
    key: str
    text: str
    quick_replies: list[str]


class DialogResult(BaseModel):
    observation: StructuredObservation
    red_flags: RedFlagResult
    red_flag_lines: list[str]
    next_question: NextQuestion | None = None
    asked_dimensions: list[str] = Field(default_factory=list)
    turn_count: int = 0
    done: bool = False
    red: bool = False
    summary: str = ""
    transcript: str = ""


def _extract(
    text: str, profile: Profile | None, baseline: Baseline | None
) -> StructuredObservation:
    return get_llm().extract_observation(text, "zh-TW", profile, baseline)


def _merge(base: StructuredObservation, extra: StructuredObservation, override: bool) -> None:
    for k, v in extra.domains.items():
        if override or k not in base.domains or base.domains[k].value is None:
            base.domains[k] = v
    for f, val in extra.flags.model_dump().items():
        if val:
            setattr(base.flags, f, True)
    for inc in extra.incident_flags:
        if inc not in base.incident_flags:
            base.incident_flags.append(inc)
    if extra.vitals_reported:
        base.vitals_reported = extra.vitals_reported
    base.seems_different = base.seems_different or extra.seems_different


def _apply_answer(
    obs: StructuredObservation,
    key: str,
    question: str,
    text: str,
    profile: Profile | None,
    baseline: Baseline | None,
    ts: datetime,
) -> None:
    if text.strip() == UNKNOWN:
        obs.followups.append(FollowupQA(question=question, answer=None, answered_unknown=True))
        return
    extra = _extract(text, profile, baseline)
    _merge(obs, extra, override=True)
    dim = key if key in DIMENSIONS else None
    normal = text.strip() in NORMAL_REPLIES or "跟平常一樣" in text or "正常" in text
    if dim and (dim not in extra.domains or normal):
        prov = Provenance(
            source="ai_extracted", author="intake_agent", ts=ts, language_original="zh-TW"
        )
        obs.domains[dim] = DimensionValue(
            value=0.0 if (normal and dim == "pain") else None,
            raw_quote=text.strip(),
            provenance=prov,
            confidence=0.9 if normal else 0.6,
            lang="zh-TW",
            direction="same" if normal else "unknown",
        )
    obs.followups.append(FollowupQA(question=question, answer=text))


def _phrase(dim: str, dv: DimensionValue) -> str:
    if dim == "intake" and isinstance(dv.value, int | float):
        v = float(dv.value)
        return (
            "吃完"
            if v >= 0.95
            else "吃一半"
            if 0.4 <= v <= 0.6
            else "幾乎沒吃"
            if v <= 0.2
            else dv.raw_quote
        )
    if dim == "sleep" and isinstance(dv.value, int | float):
        n = int(dv.value)
        return "睡得好" if n == 0 else f"晚上起來 {n} 次"
    if dv.direction == "same":
        return {
            "pain": "沒有痛",
            "skin": "皮膚沒事",
            "vitals": "沒有咳嗽或發燒",
            "elimination": "大便正常",
            "cognition": "精神跟平常一樣",
            "function": "走路跟平常一樣",
            "sleep": "睡得好",
            "intake": "吃得跟平常一樣",
        }[dim]
    return dv.raw_quote


def summarize(obs: StructuredObservation, name: str) -> str:
    parts = [_phrase(d, obs.domains[d]) for d in ASK_ORDER if d in obs.domains]
    ev = {
        "fall": "有跌倒",
        "medication_issue": "藥沒有吃好",
        "choking": "有嗆到",
        "behavior": "情緒行為跟平常不一樣",
    }
    parts += [ev[i] for i in obs.incident_flags if i in ev]
    f = obs.flags
    if f.fall_head_strike:
        parts.append("撞到頭")
    if f.cannot_get_up_after_fall:
        parts.append("站不起來")
    if f.fever_feel and "vitals" not in obs.domains:
        parts.append("摸起來燙")
    if obs.seems_different:
        parts.append("跟平常不一樣")
    unknown = [q.question for q in obs.followups if q.answered_unknown]
    body = "、".join(dict.fromkeys(parts)) if parts else "你說的我記下來了"
    tail = f"（{len(unknown)} 題不知道）" if unknown else ""
    return f"我聽到的是：{name}今天{body}{tail}。對嗎？"


def _next(obs: StructuredObservation, asked: list[str], name: str) -> NextQuestion | None:
    f = obs.flags
    # event follow-ups first (only if the answer is not already known from the words)
    for inc in obs.incident_flags:
        key = f"event:{inc}"
        if key in asked:
            continue
        if inc == "fall" and (f.fall_head_strike or f.cannot_get_up_after_fall):
            continue
        q, quick = EVENT_QUESTIONS[inc]
        return NextQuestion(key=key, text=q, quick_replies=quick)
    if obs.seems_different and not obs.domains and "event:seems_different" not in asked:
        q, quick = EVENT_QUESTIONS["seems_different"]
        return NextQuestion(key="event:seems_different", text=q, quick_replies=quick)
    # intake mentioned but without an amount → ask the amount once
    if "intake" in obs.domains and obs.domains["intake"].value is None and "intake" not in asked:
        q, quick = QUESTIONS["intake"]
        return NextQuestion(key="intake", text=q.format(name=name), quick_replies=quick)
    for dim in ASK_ORDER:
        if dim in obs.domains or dim in asked:
            continue
        q, quick = QUESTIONS[dim]
        return NextQuestion(key=dim, text=q.format(name=name), quick_replies=quick)
    return None


def run_dialog(
    turns: list[Turn],
    profile: Profile | None,
    baseline: Baseline | None,
    seems_different: bool = False,
    incidents: list[str] | None = None,
) -> DialogResult:
    ts = datetime.now(UTC)
    name = profile.code_name if profile else "他"
    if not turns:
        raise ValueError("dialog needs at least the caregiver's first sentence")
    first = turns[0].text.strip()
    obs = _extract(first, profile, baseline)
    if seems_different:
        obs.seems_different = True
    for inc in incidents or []:
        if inc not in obs.incident_flags and inc in (
            "fall",
            "medication_issue",
            "choking",
            "behavior",
        ):
            obs.incident_flags.append(inc)  # type: ignore[arg-type]
    asked: list[str] = []
    for t in turns[1:]:
        text = t.text.strip()
        if not text:
            continue
        if t.dimension:
            asked.append(t.dimension)
            key = t.dimension
            if key.startswith("event:"):
                q = EVENT_QUESTIONS.get(key[6:], ("", []))[0]
            else:
                q = QUESTIONS.get(key, ("", []))[0].format(name=name)
            _apply_answer(obs, key, q, text, profile, baseline, ts)
        else:
            _merge(obs, _extract(text, profile, baseline), override=False)
    obs.raw_text = "。".join(t.text.strip() for t in turns if t.text.strip())
    obs.unknown = [d for d in DIMENSIONS if d not in obs.domains]

    rf = evaluate(
        RedFlagInput(
            observation=obs,
            baseline_vitals=baseline.vitals_usual if baseline else None,
            on_anticoagulant=profile.on_anticoagulant if profile else False,
        )
    )
    red = rf.notify_now
    turn_count = len(asked)
    nq = None if (red or turn_count >= MAX_TURNS) else _next(obs, asked, name)
    return DialogResult(
        observation=obs,
        red_flags=rf,
        red_flag_lines=render_lines(rf),
        next_question=nq,
        asked_dimensions=asked,
        turn_count=turn_count,
        done=red or nq is None,
        red=red,
        summary=summarize(obs, name),
        transcript=obs.raw_text,
    )
