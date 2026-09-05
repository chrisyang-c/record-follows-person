"""Multi-turn intake dialog — the Intake Agent's conversation.

Turn 0 is the caregiver's own sentence. After that the agent (the model) decides EVERY
follow-up: it receives the eight-dimension state, the person's profile and baseline, what has
already been asked, the incident / red-flag facts and the remaining budget, and returns
what to ask, how to word it and a `reason` (stored in the trace). There is no hard-coded
question list, no quick replies and no rule fallback: when no model is configured or a call
fails, LLMUnavailable propagates and the UI shows the error.

A red flag never ends the dialog: the program has already notified the nurse (Path A); the
agent switches to phase "red" and asks the key facts the nurse needs before arriving; every
answer is pushed into the caregiver section the nurse is watching.

Every utterance is extracted by the same extractor (the model; the lexicon only under the
MODEL_PROVIDER=mock test double).
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel, Field
from record_schema import (
    DIMENSION_LABELS,
    DIMENSIONS,
    Baseline,
    DimensionValue,
    FollowupQA,
    Profile,
    Provenance,
    RedFlagResult,
    StructuredObservation,
)

from core.llm import LLMUnavailable, NextQuestionOut, get_llm
from core.settings import get_settings
from core.trace import trace
from record.store import get_store
from red_flags.rules import RedFlagInput, evaluate, render_lines

MAX_LLM_TURNS = 4  # routine: 追問到八維度足夠，上限 4 題
MAX_RED_TURNS = 6  # red: the key facts the nurse needs before arriving
UNKNOWN = "不知道"
RED_INTRO = "護理師馬上來，來之前先告訴我幾件事。"
RED_CLOSING = "都記下來了，護理師到了會接手。有什麼變化再跟我說。"
INCIDENT_LABEL = {
    "fall": "跌倒",
    "medication_issue": "拒藥／吐藥",
    "choking": "嗆咳",
    "behavior": "攻擊／遊走",
}


class Turn(BaseModel):
    text: str
    question: str | None = None  # the agent's question this turn answers (None = free text)
    dimension: str | None = None  # the dimension the agent said that question targeted
    phase: str | None = None  # phase the question was asked in ("routine" | "red")
    ts: str | None = None


class NextQuestion(BaseModel):
    key: str
    text: str
    dimension: str | None = None
    reason: str = ""


class Report(BaseModel):
    question: str
    answer: str
    key: str
    ts: str


class DialogResult(BaseModel):
    observation: StructuredObservation
    red_flags: RedFlagResult
    red_flag_lines: list[str] = Field(default_factory=list, description="nurse-side only")
    next_question: NextQuestion | None = None
    asked: list[str] = Field(default_factory=list, description="questions already asked")
    asked_dimensions: list[str] = Field(default_factory=list)
    turn_count: int = 0
    budget_left: int = 0
    reports: list[Report] = Field(default_factory=list)
    done: bool = False
    red: bool = False
    intro: str | None = None
    closing: str | None = None
    summary: str = ""
    transcript: str = ""


# --- extraction (cached per utterance; provenance re-stamped per turn) -------------------


def _extract_cache_key(text: str, patient_id: str) -> str:
    """Same sentence + same resident + same model/effort + same day → same extraction.
    The day is part of the key because the cached record prefix (baseline + 14-day timeline)
    the model sees changes daily."""
    s = get_settings()
    raw = "|".join(
        [
            s.MODEL_PINNED,
            s.INTAKE_REASONING_EFFORT,
            datetime.now(UTC).date().isoformat(),
            patient_id,
            text,
        ]
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]


def _extract_cache_file(patient_id: str) -> Path:
    store = get_store()
    return (store.dir(patient_id) if patient_id else store.root / "_shared") / "extract_cache.json"


def _extract_cache_load(patient_id: str) -> dict[str, str]:
    f = _extract_cache_file(patient_id)
    try:
        return json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}
    except (OSError, ValueError):
        return {}


@lru_cache(maxsize=512)
def _extract_cached(text: str, patient_id: str) -> str:
    """One model call per distinct sentence: in-process LRU in front of a per-resident JSON file
    (records/{pid}/extract_cache.json), so a later turn — or a reloaded server — only extracts
    the new sentence. Cache hits are traced as ``llm.extract_cache``."""
    key = _extract_cache_key(text, patient_id)
    disk = _extract_cache_load(patient_id)
    if key in disk:
        trace("llm.extract_cache", hit=True, patient_id=patient_id, text=text[:60])
        return disk[key]
    store = get_store()
    profile = store.load_profile(patient_id) if patient_id and store.exists(patient_id) else None
    baseline = store.load_baseline(patient_id) if profile else None
    out = get_llm().extract_observation(text, "zh-TW", profile, baseline).model_dump_json()
    if get_settings().effective_provider != "mock":  # test doubles are scripted; never persist
        f = _extract_cache_file(patient_id)
        f.parent.mkdir(parents=True, exist_ok=True)
        disk = _extract_cache_load(patient_id)
        disk[key] = out
        f.write_text(json.dumps(disk, ensure_ascii=False), encoding="utf-8")
    return out


def _extract(
    text: str, profile: Profile | None, baseline: Baseline | None
) -> StructuredObservation:
    pid = profile.patient_id if profile else ""
    # normalise the cache key: the same sentence must not be extracted twice (one model call)
    obs = StructuredObservation.model_validate_json(_extract_cached(text.strip(), pid))
    ts = datetime.now(UTC)
    for dv in obs.domains.values():
        dv.provenance = Provenance(
            source="ai_extracted", author="intake_agent", ts=ts, language_original="zh-TW"
        )
    return obs


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
    turn: Turn,
    profile: Profile | None,
    baseline: Baseline | None,
    ts: datetime,
) -> None:
    text = turn.text.strip()
    question = turn.question or "（照護者補充）"
    if text == UNKNOWN:
        obs.followups.append(FollowupQA(question=question, answer=None, answered_unknown=True))
        return
    extra = _extract(text, profile, baseline)
    _merge(obs, extra, override=True)
    dim = turn.dimension if turn.dimension in DIMENSIONS else None
    normal = (
        "跟平常一樣" in text or "正常" in text or text in {"沒有", "都沒有", "沒有痛", "睡得好"}
    )
    if dim and (dim not in extra.domains or normal):
        # the agent asked about this dimension; keep the caregiver's words under it
        obs.domains[dim] = DimensionValue(
            value=0.0
            if (normal and dim == "pain")
            else obs.domains.get(
                dim,
                DimensionValue(
                    raw_quote=text,
                    provenance=Provenance(source="ai_extracted", author="intake_agent", ts=ts),
                    confidence=0.6,
                    lang="zh-TW",
                ),
            ).value,
            raw_quote=text,
            provenance=Provenance(
                source="ai_extracted", author="intake_agent", ts=ts, language_original="zh-TW"
            ),
            confidence=0.9 if normal else 0.6,
            lang="zh-TW",
            direction="same"
            if normal
            else (extra.domains[dim].direction if dim in extra.domains else "unknown"),
        )
    obs.followups.append(FollowupQA(question=question, answer=text))


# --- summary in the caregiver's own words -----------------------------------------------


def _phrase(dim: str, dv: DimensionValue) -> str:
    if dim == "intake" and isinstance(dv.value, int | float):
        v = float(dv.value)
        if v >= 0.95:
            return "吃完"
        if 0.4 <= v <= 0.6:
            return "吃一半"
        if v <= 0.2:
            return "幾乎沒吃"
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
    parts = [_phrase(d, obs.domains[d]) for d in DIMENSIONS if d in obs.domains]
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


# --- the agent's context ----------------------------------------------------------------------


def _context(
    obs: StructuredObservation,
    profile: Profile | None,
    baseline: Baseline | None,
    asked: list[tuple[str, str]],
    red: RedFlagResult,
    phase: str,
    budget: int,
) -> dict:
    label = lambda d: DIMENSION_LABELS[d]["zh-TW"]  # noqa: E731
    prof = "（無 profile）"
    base = "（無基線）"
    if profile:
        age = datetime.now(UTC).year - profile.birth_year
        meds = "、".join(
            f"{m.name}{'（抗凝血）' if m.is_anticoagulant else ''}" for m in profile.medications
        )
        prof = (
            f"{profile.code_name}，{age} 歲；"
            f"慢性病：{'、'.join(c.display for c in profile.conditions) or '無'}；"
            f"用藥：{meds or '無'}；{profile.one_liner}"
        )
    if baseline:
        base = "；".join(
            f"{label(e.dimension)}：{e.description}" for e in baseline.entries if e.valid_to is None
        )
    known = "；".join(
        f"{label(d)}：「{dv.raw_quote}」({dv.direction})" for d, dv in obs.domains.items()
    )
    facts = [f for h in red.hits for f in h.facts]
    facts += [INCIDENT_LABEL.get(i, i) for i in obs.incident_flags]
    facts += [k for k, v in obs.flags.model_dump().items() if v]
    if obs.seems_different:
        facts.append("照護者說跟平常不一樣")
    from core.llm import record_prefix

    return {
        "phase": phase,
        "profile": prof,
        "baseline": base,
        "record": record_prefix(profile, baseline),
        "said": obs.raw_text.split("。")[0],
        "known": known,
        "unknown": [label(d) for d in DIMENSIONS if d not in obs.domains],
        "facts": facts,
        "asked": [f"{q}→{a}" for q, a in asked],
        "budget": budget,
    }


_LABEL_TO_KEY = {v["zh-TW"]: k for k, v in DIMENSION_LABELS.items()}


def _norm_dim(d: str | None) -> str | None:
    """The model may answer with the zh label instead of the key; accept both."""
    if not d:
        return None
    d = d.strip()
    return d if d in DIMENSIONS else _LABEL_TO_KEY.get(d)


def _same_question(a: str, b: str) -> bool:
    x, y = a.strip().rstrip("？?。"), b.strip().rstrip("？?。")
    return bool(x) and (x == y or x in y or y in x)


def _plan(ctx: dict, known_dims: set[str], phase: str, n: int) -> NextQuestion | None:
    """Ask the model; validate its choice (known dimension / repeated question) and give it one
    retry with the constraint restated. A second invalid decision is an error, not a fallback."""
    llm = get_llm()
    asked_q = [a.split("→", 1)[0] for a in ctx.get("asked") or []]

    def invalid(o: NextQuestionOut) -> str | None:
        if not o.ask:
            return None
        if not o.question.strip():
            return "question 是空的"
        if any(_same_question(o.question, q) for q in asked_q):
            return f"「{o.question.strip()}」已經問過（照護者已回答），不要重複，換一題或 ask=false"
        d = _norm_dim(o.dimension)
        if phase != "red" and d in known_dims:
            return f"「{DIMENSION_LABELS[d]['zh-TW']}」已知，不要再問，換一個未知維度或 ask=false"
        return None

    out = llm.next_question(ctx)
    why = invalid(out)
    if why:
        out = llm.next_question({**ctx, "note": why})
        why = invalid(out)
    if not out.ask:
        return None
    if why:
        raise LLMUnavailable(f"agent 回傳無效的追問決定：{why}（見 /trace）")
    return NextQuestion(
        key=f"q{n}",
        text=out.question.strip(),
        dimension=_norm_dim(out.dimension),
        reason=out.reason,
    )


def build_observation(
    turns: list[Turn],
    profile: Profile | None,
    baseline: Baseline | None,
    seems_different: bool = False,
    incidents: list[str] | None = None,
) -> tuple[StructuredObservation, list[tuple[str, str]], list[str], list[Report]]:
    """Merge the caregiver's turns into one observation (each utterance extracted by the model)."""
    ts = datetime.now(UTC)
    if not turns:
        raise ValueError("dialog needs at least the caregiver's first sentence")
    obs = _extract(turns[0].text.strip(), profile, baseline)
    if seems_different:
        obs.seems_different = True
    for inc in incidents or []:
        if inc not in obs.incident_flags and inc in INCIDENT_LABEL:
            obs.incident_flags.append(inc)  # type: ignore[arg-type]
    asked: list[tuple[str, str]] = []
    asked_dims: list[str] = []
    reports: list[Report] = []
    for i, t in enumerate(turns[1:], start=1):
        text = t.text.strip()
        if not text:
            continue
        _apply_answer(obs, t, profile, baseline, ts)
        if t.question:
            asked.append((t.question, text))
            if t.dimension:
                asked_dims.append(t.dimension)
        reports.append(
            Report(
                question=t.question or "（照護者補充）",
                answer=text,
                key=f"q{i}",
                ts=t.ts or ts.isoformat(),
            )
        )
    obs.raw_text = "。".join(t.text.strip() for t in turns if t.text.strip())
    obs.unknown = [d for d in DIMENSIONS if d not in obs.domains]
    return obs, asked, asked_dims, reports


def evaluate_red(
    obs: StructuredObservation, profile: Profile | None, baseline: Baseline | None
) -> RedFlagResult:
    return evaluate(
        RedFlagInput(
            observation=obs,
            baseline_vitals=baseline.vitals_usual if baseline else None,
            on_anticoagulant=profile.on_anticoagulant if profile else False,
        )
    )


def plan_question(
    obs: StructuredObservation,
    profile: Profile | None,
    baseline: Baseline | None,
    asked: list[tuple[str, str]],
    rf: RedFlagResult,
) -> tuple[NextQuestion | None, int]:
    """Ask the model what to ask next (or nothing). Returns (question, budget_left)."""
    red = rf.notify_now
    phase = "red" if red else "routine"
    budget = (MAX_RED_TURNS if red else MAX_LLM_TURNS) - len(asked)
    nq = None
    if budget > 0:
        ctx = _context(obs, profile, baseline, asked, rf, phase, budget)
        nq = _plan(ctx, set(obs.domains), phase, len(asked) + 1)
    return nq, max(budget - (1 if nq else 0), 0)


def run_dialog(
    turns: list[Turn],
    profile: Profile | None,
    baseline: Baseline | None,
    seems_different: bool = False,
    incidents: list[str] | None = None,
    plan_next: bool = True,
) -> DialogResult:
    name = profile.code_name if profile else "他"
    obs, asked, asked_dims, reports = build_observation(
        turns, profile, baseline, seems_different, incidents
    )
    rf = evaluate_red(obs, profile, baseline)
    red = rf.notify_now
    phase = "red" if red else "routine"
    nq: NextQuestion | None = None
    budget_left = (MAX_RED_TURNS if red else MAX_LLM_TURNS) - len(asked)
    if plan_next:
        nq, budget_left = plan_question(obs, profile, baseline, asked, rf)
    was_red = any(t.phase == "red" for t in turns[1:])
    intro = RED_INTRO if (red and nq is not None and not was_red) else None
    closing = RED_CLOSING if (red and nq is None) else None
    trace(
        "intake.turn",
        patient_id=profile.patient_id if profile else None,
        turns=len(turns),
        phase=phase,
        red=red,
        asked=[q for q, _ in asked],
        next=nq.model_dump() if nq else None,
        domains=list(obs.domains),
        budget_left=budget_left,
    )
    return DialogResult(
        observation=obs,
        red_flags=rf,
        red_flag_lines=render_lines(rf),
        next_question=nq,
        asked=[q for q, _ in asked],
        asked_dimensions=asked_dims,
        turn_count=len(asked),
        budget_left=max(budget_left, 0),
        reports=reports,
        done=nq is None,
        red=red,
        intro=intro,
        closing=closing,
        summary=summarize(obs, name),
        transcript=obs.raw_text,
    )
