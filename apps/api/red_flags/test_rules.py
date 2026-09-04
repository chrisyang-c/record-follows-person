"""Three cases per rule: hit / miss / boundary. Pure code — no network, no LLM."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest
from record_schema import ObservationFlags, StructuredObservation, Vitals

from red_flags.rules import RULES, RedFlagInput, evaluate, render_lines


def obs(flags: ObservationFlags | None = None, incidents=(), reported: Vitals | None = None):
    return StructuredObservation(
        raw_text="x",
        language="zh-TW",
        flags=flags or ObservationFlags(),
        incident_flags=list(incidents),
        vitals_reported=reported,
    )


def ids(result):
    return {h.rule_id for h in result.hits}


# RF01 意識 ---------------------------------------------------------------------
def test_rf01_hit():
    r = evaluate(RedFlagInput(observation=obs(ObservationFlags(new_confusion_or_drowsiness=True))))
    assert "RF01" in ids(r) and r.notify_now


def test_rf01_miss():
    assert "RF01" not in ids(evaluate(RedFlagInput(observation=obs())))


def test_rf01_boundary_consciousness_alone():
    r = evaluate(RedFlagInput(observation=obs(ObservationFlags(consciousness_change=True))))
    assert "RF01" in ids(r) and "RF06" not in ids(r)


# RF02 體溫 ---------------------------------------------------------------------
@pytest.mark.parametrize("t,hit", [(38.5, True), (38.4, False), (34.9, True), (35.0, False)])
def test_rf02_boundaries(t, hit):
    r = evaluate(RedFlagInput(observation=obs(), vitals=Vitals(temp_c=t)))
    assert ("RF02" in ids(r)) is hit


def test_rf02_uses_caregiver_reported_when_not_measured():
    r = evaluate(RedFlagInput(observation=obs(reported=Vitals(temp_c=39.0))))
    assert "RF02" in ids(r)


def test_rf02_measured_overrides_reported():
    r = evaluate(
        RedFlagInput(observation=obs(reported=Vitals(temp_c=39.0)), vitals=Vitals(temp_c=37.2))
    )
    assert "RF02" not in ids(r)


# RF03 呼吸 ---------------------------------------------------------------------
@pytest.mark.parametrize("rr,hit", [(7, True), (8, False), (24, False), (25, True)])
def test_rf03_rr_boundaries(rr, hit):
    assert ("RF03" in ids(evaluate(RedFlagInput(observation=obs(), vitals=Vitals(rr=rr))))) is hit


@pytest.mark.parametrize("spo2,hit", [(91, True), (92, False)])
def test_rf03_spo2_absolute(spo2, hit):
    assert (
        "RF03" in ids(evaluate(RedFlagInput(observation=obs(), vitals=Vitals(spo2=spo2))))
    ) is hit


def test_rf03_spo2_drop_vs_baseline():
    hit = evaluate(
        RedFlagInput(observation=obs(), vitals=Vitals(spo2=94), baseline_vitals=Vitals(spo2=97))
    )
    miss = evaluate(
        RedFlagInput(observation=obs(), vitals=Vitals(spo2=95), baseline_vitals=Vitals(spo2=97))
    )
    assert "RF03" in ids(hit) and "RF03" not in ids(miss)


# RF04 血壓心率 -----------------------------------------------------------------
@pytest.mark.parametrize("sbp,hit", [(89, True), (90, False), (220, False), (221, True)])
def test_rf04_sbp(sbp, hit):
    assert ("RF04" in ids(evaluate(RedFlagInput(observation=obs(), vitals=Vitals(sbp=sbp))))) is hit


@pytest.mark.parametrize("hr,hit", [(39, True), (40, False), (130, False), (131, True)])
def test_rf04_hr(hr, hit):
    assert ("RF04" in ids(evaluate(RedFlagInput(observation=obs(), vitals=Vitals(hr=hr))))) is hit


# RF05 跌倒 ---------------------------------------------------------------------
def test_rf05_fall_with_head_strike():
    r = evaluate(
        RedFlagInput(observation=obs(ObservationFlags(fall_head_strike=True), incidents=["fall"]))
    )
    assert "RF05" in ids(r)


def test_rf05_fall_on_anticoagulant():
    r = evaluate(RedFlagInput(observation=obs(incidents=["fall"]), on_anticoagulant=True))
    assert "RF05" in ids(r)


def test_rf05_fall_without_either_is_not_red():
    r = evaluate(RedFlagInput(observation=obs(incidents=["fall"])))
    assert "RF05" not in ids(r)


def test_rf05_head_strike_flag_without_fall_event_is_ignored():
    r = evaluate(RedFlagInput(observation=obs(ObservationFlags(fall_head_strike=True))))
    assert "RF05" not in ids(r)


# RF06 三合一 -------------------------------------------------------------------
def test_rf06_hit():
    r = evaluate(
        RedFlagInput(
            observation=obs(ObservationFlags(new_confusion_or_drowsiness=True)),
            vitals=Vitals(temp_c=38.2, hr=112),
        )
    )
    assert "RF06" in ids(r)


def test_rf06_two_of_three_miss():
    r = evaluate(RedFlagInput(observation=obs(), vitals=Vitals(temp_c=38.2, hr=112)))
    assert "RF06" not in ids(r)


def test_rf06_boundary_hr_100_not_tachy_but_fever_feel_counts():
    r = evaluate(
        RedFlagInput(
            observation=obs(ObservationFlags(fever_feel=True, consciousness_change=True)),
            vitals=Vitals(hr=100),
        )
    )
    assert "RF06" not in ids(r)
    r2 = evaluate(
        RedFlagInput(
            observation=obs(ObservationFlags(fever_feel=True, consciousness_change=True)),
            vitals=Vitals(hr=101),
        )
    )
    assert "RF06" in ids(r2)


# RF07 觀察 ---------------------------------------------------------------------
def test_rf07_observe_not_notify():
    r = evaluate(RedFlagInput(observation=obs(ObservationFlags(intake_sudden_drop=True))))
    assert "RF07" in ids(r) and r.observe and not r.notify_now


def test_rf07_no_urine():
    r = evaluate(RedFlagInput(observation=obs(ObservationFlags(no_urine_24h=True))))
    assert "RF07" in ids(r)


def test_rf07_miss():
    assert "RF07" not in ids(evaluate(RedFlagInput(observation=obs())))


# RF08–RF10 關鍵字硬條件 ---------------------------------------------------------
@pytest.mark.parametrize(
    "flags,incidents,rule",
    [
        (ObservationFlags(chest_pain=True), (), "RF08"),
        (ObservationFlags(breathing_difficulty=True), (), "RF09"),
        (ObservationFlags(cannot_get_up_after_fall=True), ("fall",), "RF10"),
    ],
)
def test_keyword_rules_hit(flags, incidents, rule):
    assert rule in ids(evaluate(RedFlagInput(observation=obs(flags, incidents))))


def test_keyword_rules_miss():
    assert not ids(evaluate(RedFlagInput(observation=obs())))


def test_rf10_requires_fall_event():
    r = evaluate(RedFlagInput(observation=obs(ObservationFlags(cannot_get_up_after_fall=True))))
    assert "RF10" not in ids(r)


# 輸出與治理 --------------------------------------------------------------------
def test_render_has_no_level_or_score():
    r = evaluate(
        RedFlagInput(observation=obs(ObservationFlags(chest_pain=True)), vitals=Vitals(temp_c=39))
    )
    text = "\n".join(render_lines(r))
    assert "建議" in text and "非診斷" in text
    for banned in ("等級", "分數", "Level", "score", "檢傷 1", "檢傷 2", "第一級", "紅色警戒"):
        assert banned not in text


def test_every_rule_requires_validation_and_has_id():
    assert len({r.id for r in RULES}) == len(RULES)
    assert all(r.requires_validation for r in RULES)


def test_rules_module_never_calls_an_llm():
    src = Path(__file__).with_name("rules.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    imported = {
        (n.module or "") if isinstance(n, ast.ImportFrom) else a.name
        for n in ast.walk(tree)
        if isinstance(n, ast.ImportFrom | ast.Import)
        for a in (n.names if isinstance(n, ast.Import) else [None])
    }
    banned = ("langchain", "anthropic", "openai", "deepagents", "core.llm", "httpx", "requests")
    assert not any(any(b in m for b in banned) for m in imported if m)
    assert "llm" not in src.lower().replace("no llm", "").replace("llm call is allowed", "")
