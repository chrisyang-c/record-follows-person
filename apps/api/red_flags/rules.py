"""Red-flag rules — PURE CODE. No LLM call is allowed in this module (CLAUDE.md §1.4, §11).

Every rule: id, description, condition(), action, requires_validation=True.
Output only states observed facts + "建議聯絡護理師". No level, no score, no diagnosis,
no triage grade. Each rule has unit tests (hit / miss / boundary) in test_rules.py.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel
from record_schema import (
    RedFlagHit,
    RedFlagResult,
    SensorEvent,
    StructuredObservation,
    Vitals,
    VitalsBands,
)

from baseline.vitals_band import METRICS as BAND_METRICS
from baseline.vitals_band import departure

Action = Literal["notify_now", "observe"]

# Channel 4 hard conditions (the only sensor facts that notify by themselves; the rest is
# verified by a person). Thresholds are code, not model output.
SENSOR_STILL_S = 60
SENSOR_SPO2_MIN = 92


class RedFlagInput(BaseModel):
    observation: StructuredObservation
    vitals: Vitals | None = None
    baseline_vitals: Vitals | None = None
    on_anticoagulant: bool = False
    sensor: SensorEvent | None = None
    caregiver_unreachable: bool = False

    # Optional: this person's own measured ranges (baseline/vitals_band.py). When absent
    # every rule below behaves exactly as before — RF13 is the only rule that reads it.
    vitals_bands: VitalsBands | None = None
    recent_vitals: list[Vitals] = []

    def merged_vitals(self) -> Vitals:
        """Nurse-measured values take precedence over caregiver-reported numbers."""
        reported = self.observation.vitals_reported or Vitals()
        measured = self.vitals or Vitals()
        data = reported.model_dump()
        for k, v in measured.model_dump().items():
            if v is not None:
                data[k] = v
        return Vitals(**data)


Condition = Callable[[RedFlagInput], list[str]]


@dataclass(frozen=True)
class Rule:
    id: str
    description: str
    condition: Condition
    action: Action
    requires_validation: bool = True


# --- conditions: each returns the list of observed facts (empty = not hit) -----------------


def _consciousness(inp: RedFlagInput) -> list[str]:
    f = inp.observation.flags
    facts = []
    if f.consciousness_change:
        facts.append("照護者回報意識狀態改變")
    if f.new_confusion_or_drowsiness:
        facts.append("照護者回報新發生的混亂或嗜睡")
    return facts


def _temperature(inp: RedFlagInput) -> list[str]:
    t = inp.merged_vitals().temp_c
    if t is None:
        return []
    if t >= 38.5:
        return [f"體溫 {t:.1f}°C（≥38.5）"]
    if t < 35.0:
        return [f"體溫 {t:.1f}°C（<35）"]
    return []


def _respiration(inp: RedFlagInput) -> list[str]:
    v = inp.merged_vitals()
    facts = []
    if v.rr is not None and (v.rr < 8 or v.rr >= 25):
        facts.append(f"呼吸 {v.rr}／分")
    if v.spo2 is not None:
        if v.spo2 < 92:
            facts.append(f"SpO₂ {v.spo2}%（<92）")
        base = inp.baseline_vitals.spo2 if inp.baseline_vitals else None
        if base is not None and base - v.spo2 >= 3:
            facts.append(f"SpO₂ {v.spo2}%，較基線 {base}% 降 {base - v.spo2}%")
    return facts


def _bp_hr(inp: RedFlagInput) -> list[str]:
    v = inp.merged_vitals()
    facts = []
    if v.sbp is not None and (v.sbp < 90 or v.sbp > 220):
        facts.append(f"收縮壓 {v.sbp} mmHg")
    if v.hr is not None and (v.hr < 40 or v.hr > 130):
        facts.append(f"心率 {v.hr}／分")
    return facts


def _fall(inp: RedFlagInput) -> list[str]:
    obs = inp.observation
    if "fall" not in obs.incident_flags:
        return []
    facts = []
    if obs.flags.fall_head_strike:
        facts.append("跌倒且頭部撞擊")
    if inp.on_anticoagulant:
        facts.append("跌倒且目前使用抗凝血劑")
    return facts


def _sepsis_like_triad(inp: RedFlagInput) -> list[str]:
    """發燒＋心跳快＋意識改變同時出現（三者皆為觀察事實，不是診斷）。"""
    v = inp.merged_vitals()
    f = inp.observation.flags
    fever = (v.temp_c is not None and v.temp_c >= 38.0) or f.fever_feel
    tachy = v.hr is not None and v.hr > 100
    consc = f.consciousness_change or f.new_confusion_or_drowsiness
    if fever and tachy and consc:
        parts = []
        parts.append(f"體溫 {v.temp_c:.1f}°C" if v.temp_c is not None else "照護者覺得發燒")
        parts.append(f"心率 {v.hr}／分")
        parts.append("意識或認知有改變")
        return ["同時出現：" + "、".join(parts)]
    return []


def _chest_pain(inp: RedFlagInput) -> list[str]:
    return ["照護者回報胸痛"] if inp.observation.flags.chest_pain else []


def _breathing_difficulty(inp: RedFlagInput) -> list[str]:
    return ["照護者回報呼吸困難／喘"] if inp.observation.flags.breathing_difficulty else []


def _cannot_get_up(inp: RedFlagInput) -> list[str]:
    f = inp.observation.flags
    if "fall" in inp.observation.incident_flags and f.cannot_get_up_after_fall:
        return ["跌倒後無法自行起身"]
    return []


def _sensor_hard(inp: RedFlagInput) -> list[str]:
    """感測事件只做硬條件：靜止 ≥ SENSOR_STILL_S 秒，或 SpO₂ < SENSOR_SPO2_MIN。其餘交人驗證。"""
    e = inp.sensor
    if e is None:
        return []
    facts = []
    if e.still_seconds >= SENSOR_STILL_S:
        facts.append(f"感測器：可能跌倒後靜止 {e.still_seconds} 秒")
    if e.spo2_after is not None and e.spo2_after < SENSOR_SPO2_MIN:
        facts.append(f"感測器：可能跌倒後 SpO₂ {e.spo2_after}%")
    return facts


def _unreachable(inp: RedFlagInput) -> list[str]:
    if inp.sensor is not None and inp.caregiver_unreachable:
        return ["感測器：可能跌倒，照護者回報聯絡不上他"]
    return []


def _personal_band(inp: RedFlagInput) -> list[str]:
    """Departure from this person's own measured range (not a population threshold).

    RF02–RF04 ask "is this value dangerous for anyone". This asks "is this value unusual
    for him". P001's usual systolic is 138: a reading of 118 clears every population
    threshold and is a real drop for him.

    Deliberately ``observe``, not ``notify_now``. A departure from one's own range is the
    early, quiet signal — putting it in the red banner would drown the rules that mean
    "call the nurse now", and a banner people learn to ignore protects nobody.
    """
    bands = inp.vitals_bands
    if bands is None:
        return []
    current = inp.merged_vitals()
    facts: list[str] = []
    for metric in BAND_METRICS:
        band = bands.get(metric)
        value = getattr(current, metric, None)
        if band is None or value is None:
            continue
        recent = [
            float(v) for v in (getattr(m, metric, None) for m in inp.recent_vitals) if v is not None
        ]
        line = departure(band, float(value), recent=recent or None)
        if line:
            facts.append(line)
    return facts


def _observe_only(inp: RedFlagInput) -> list[str]:
    f = inp.observation.flags
    facts = []
    if f.intake_sudden_drop:
        facts.append("進食量驟降")
    if f.no_urine_24h:
        facts.append("24 小時未排尿")
    return facts


RULES: tuple[Rule, ...] = (
    Rule("RF01", "意識改變、新發生混亂或嗜睡", _consciousness, "notify_now"),
    Rule("RF02", "體溫 ≥38.5°C 或 <35°C", _temperature, "notify_now"),
    Rule("RF03", "呼吸 <8 或 ≥25／分；SpO₂ <92% 或較基線降 ≥3%", _respiration, "notify_now"),
    Rule("RF04", "收縮壓 <90 或 >220；心率 <40 或 >130", _bp_hr, "notify_now"),
    Rule("RF05", "跌倒且頭部撞擊或使用抗凝血劑", _fall, "notify_now"),
    Rule("RF06", "發燒＋心跳快＋意識改變同時出現", _sepsis_like_triad, "notify_now"),
    Rule("RF07", "進食量驟降、24h 未排尿（記錄觀察）", _observe_only, "observe"),
    Rule("RF08", "胸痛", _chest_pain, "notify_now"),
    Rule("RF09", "呼吸困難", _breathing_difficulty, "notify_now"),
    Rule("RF10", "跌倒後無法起身", _cannot_get_up, "notify_now"),
    Rule(
        "RF11",
        "感測：可能跌倒後靜止 ≥60 秒或 SpO₂ <92%（硬條件，其餘交人驗證）",
        _sensor_hard,
        "notify_now",
    ),
    Rule("RF12", "感測：可能跌倒且照護者回報聯絡不上", _unreachable, "notify_now"),
    Rule(
        "RF13",
        "生理值偏離他自己平常的量測範圍（記錄觀察）",
        _personal_band,
        "observe",
    ),
)

DISCLAIMER = "需護理師／醫師驗證；非診斷、非檢傷分級。"


def evaluate(inp: RedFlagInput) -> RedFlagResult:
    hits: list[RedFlagHit] = []
    for rule in RULES:
        facts = rule.condition(inp)
        if facts:
            hits.append(
                RedFlagHit(
                    rule_id=rule.id,
                    description=rule.description,
                    facts=facts,
                    action=rule.action,
                    requires_validation=rule.requires_validation,
                )
            )
    return RedFlagResult(
        hits=hits,
        notify_now=any(h.action == "notify_now" for h in hits),
        observe=any(h.action == "observe" for h in hits),
        disclaimer=DISCLAIMER,
    )


def render_lines(result: RedFlagResult) -> list[str]:
    """Human-facing lines: observed facts + suggested action. No level, no score."""
    lines: list[str] = []
    for h in result.hits:
        suggestion = (
            "建議立即聯絡護理師" if h.action == "notify_now" else "記錄並持續觀察，交班時告知護理師"
        )
        lines.append(f"觀察到：{'；'.join(h.facts)} → {suggestion}")
    if result.hits:
        lines.append(DISCLAIMER)
    return lines
