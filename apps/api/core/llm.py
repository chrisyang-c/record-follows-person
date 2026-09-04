"""All LLM calls live here. Nothing else in apps/api may import langchain/anthropic.

Two implementations behind one interface:
  * MockLLM      — deterministic keyword extraction / templating. No network. Used when
                   MODEL_PROVIDER=mock, by tests, eval and CI, and whenever the provider key
                   is missing.
  * ChatModelLLM — any LangChain chat model from settings.get_model() (ChatOpenAI when
                   MODEL_PROVIDER=openai, ChatAnthropic when anthropic), pinned to MODEL_PINNED,
                   temperature=0. Falls back to MockLLM per-call if the model call fails.

Hard rules baked in regardless of implementation (CLAUDE.md §1.3):
  * extraction never adds judgement; every DimensionValue.raw_quote must be a substring
    of the caregiver's text (hallucination guard drops anything else);
  * ISBAR "A" from AI is only change-vs-baseline; ISBAR "R" from AI is only questions;
  * no diagnosis words, no treatment suggestions, no triage grade numbers.
"""

from __future__ import annotations

import logging
import re
from datetime import UTC, datetime
from functools import lru_cache
from typing import Any

from pydantic import BaseModel, Field
from record_schema import (
    DIMENSION_LABELS,
    ISBAR,
    Baseline,
    BaselineDelta,
    DimensionValue,
    FollowupQA,
    Lang,
    MinimalSBAR,
    Profile,
    Provenance,
    StructuredObservation,
)

from core.deidentify import deidentify
from core.settings import get_settings
from ingest.lexicon import extract_with_lexicon

log = logging.getLogger(__name__)

INCIDENT_LABELS_ZH = {
    "fall": "跌倒",
    "medication_issue": "拒藥／吐藥",
    "choking": "嗆咳",
    "behavior": "攻擊／遊走",
}

BANNED_DIAGNOSTIC_TERMS = (
    "肺炎",
    "中風",
    "敗血",
    "感染",
    "心肌梗塞",
    "脫水",
    "譫妄",
    "診斷",
    "疑似",
    "建議給藥",
    "建議使用",
    "應投予",
    "檢傷",
    "第一級",
    "第二級",
    "第三級",
    "level 1",
    "level 2",
    "pneumonia",
    "stroke",
    "sepsis",
    "infection",
    "dehydration",
    "delirium",
    "diagnos",
)


def scrub_clinical_language(text: str) -> str:
    """Belt-and-braces: strip diagnosis / treatment / triage vocabulary from AI output."""
    out = text
    for term in BANNED_DIAGNOSTIC_TERMS:
        out = re.sub(re.escape(term), "［已移除：非 AI 可寫內容］", out, flags=re.IGNORECASE)
    return out


def _guard_quotes(obs: StructuredObservation) -> StructuredObservation:
    """Drop any dimension whose raw_quote is not literally in the caregiver's text."""
    keep: dict[str, DimensionValue] = {}
    for k, dv in obs.domains.items():
        if dv.raw_quote and dv.raw_quote in obs.raw_text:
            keep[k] = dv
        else:
            log.warning("dropping %s: raw_quote %r not in text", k, dv.raw_quote)
    obs.domains = keep
    return obs


# ---------------------------------------------------------------------------
# Interface
# ---------------------------------------------------------------------------


class LLM:
    name = "base"

    def extract_observation(
        self, text: str, lang: Lang, profile: Profile | None, baseline: Baseline | None
    ) -> StructuredObservation:
        raise NotImplementedError

    def minimal_sbar(self, obs: StructuredObservation, deltas: list[BaselineDelta]) -> MinimalSBAR:
        raise NotImplementedError

    def draft_isbar(
        self,
        profile: Profile,
        baseline: Baseline,
        obs: StructuredObservation,
        deltas: list[BaselineDelta],
        recent_lines: list[str],
    ) -> ISBAR:
        raise NotImplementedError

    def family_notification(self, profile: Profile, what_happened: str, route_text: str) -> str:
        raise NotImplementedError

    def translate_lines(self, lines_zh: list[str], lang: Lang) -> list[str]:
        raise NotImplementedError


# ---------------------------------------------------------------------------
# Mock — deterministic
# ---------------------------------------------------------------------------


def _delta_text(d: BaselineDelta) -> str:
    label = DIMENSION_LABELS[d.domain]["zh-TW"]
    arrow = {
        "down": "較平常減少",
        "up": "較平常增加",
        "same": "與平常相同",
        "unknown": "與平常不同",
    }[d.direction]
    mag = f"（幅度約 {d.magnitude:.0%}）" if d.magnitude is not None else ""
    days = f"，持續 {d.days} 天" if d.days > 1 else ""
    return f"{label}{arrow}{mag}{days}"  # the baseline description itself is shown next to it


class MockLLM(LLM):
    name = "mock"

    def extract_observation(self, text, lang, profile=None, baseline=None):
        obs = extract_with_lexicon(text, lang)
        return _guard_quotes(obs)

    def minimal_sbar(self, obs, deltas):
        quotes = [dv.raw_quote for dv in obs.domains.values()][:3]
        s = (
            "照護者說：「" + "」「".join(quotes) + "」"
            if quotes
            else f"照護者說：「{obs.raw_text}」"
        )
        if obs.seems_different:
            s += "（並按了「跟平常不一樣」）"
        a = (
            "；".join(_delta_text(d) for d in deltas if d.direction != "same")
            or "與基線相比沒有明顯變化"
        )
        return MinimalSBAR(s=s, a_change_vs_baseline=a, status="draft", author="ai")

    def draft_isbar(self, profile, baseline, obs, deltas, recent_lines):
        age = datetime.now(UTC).year - profile.birth_year
        conds = "、".join(c.display for c in profile.conditions) or "無登錄慢性病"
        identity = f"{profile.code_name}，{age} 歲，{profile.room} 床；{conds}。"
        quotes = (
            "、".join(f"「{dv.raw_quote}」" for dv in obs.domains.values()) or f"「{obs.raw_text}」"
        )
        situation = f"照護者（{profile.caregiver_code_name}，{obs.language}）回報：{quotes}"
        if obs.incident_flags:
            situation += "；事件：" + "、".join(
                INCIDENT_LABELS_ZH.get(i, i) for i in obs.incident_flags
            )
        if obs.vitals_reported and any(
            v is not None for v in obs.vitals_reported.model_dump().values()
        ):
            vr = obs.vitals_reported
            parts = [
                f"體溫 {vr.temp_c}" if vr.temp_c is not None else "",
                f"血壓 {vr.sbp}/{vr.dbp}" if vr.sbp is not None else "",
                f"心率 {vr.hr}" if vr.hr is not None else "",
                f"SpO₂ {vr.spo2}" if vr.spo2 is not None else "",
            ]
            situation += "；照護者報的數值：" + "、".join(p for p in parts if p)
        base_lines = [
            f"{DIMENSION_LABELS[e.dimension]['zh-TW']}：{e.description}"
            for e in baseline.entries
            if e.valid_to is None
        ]
        meds = "、".join(f"{m.name} {m.dose} {m.schedule}" for m in profile.medications) or "無"
        allergies = "、".join(a.substance for a in profile.allergies) or "無"
        background = (
            f"平常：{'；'.join(base_lines)}。用藥：{meds}。過敏：{allergies}。"
            f"DNR：{'是' if profile.dnr else '否'}。"
            + (f"近期：{'；'.join(recent_lines[:3])}。" if recent_lines else "")
        )
        change = (
            "；".join(_delta_text(d) for d in deltas if d.direction != "same")
            or "與基線相比沒有明顯變化"
        )
        questions = self._questions(obs, deltas)
        return ISBAR(
            identity=identity,
            situation=situation,
            background=background,
            ai_change_vs_baseline=scrub_clinical_language(change),
            ai_questions_for_nurse=[scrub_clinical_language(q) for q in questions],
            status="draft",
            author="ai",
        )

    @staticmethod
    def _questions(obs: StructuredObservation, deltas: list[BaselineDelta]) -> list[str]:
        qs: list[str] = []
        f = obs.flags
        if "fall" in obs.incident_flags:
            qs.append("請確認：跌倒後有無頭部撞擊、疼痛部位、能否自行站立？")
        if f.fever_feel or (obs.vitals_reported and obs.vitals_reported.temp_c):
            qs.append("請確認：現場體溫、心率與呼吸次數？")
        if f.new_confusion_or_drowsiness or f.consciousness_change:
            qs.append("請確認：意識狀態與平常相比如何（可喚醒、對答、認人）？")
        for d in deltas:
            if d.domain == "intake" and d.direction == "down":
                qs.append("請確認：飲水量與尿量是否同步減少？口腔或吞嚥有無異常？")
            if d.domain == "sleep" and d.direction == "up":
                qs.append("請確認：夜間醒來的原因（疼痛、如廁、環境）？")
            if d.domain == "skin":
                qs.append("請確認：皮膚變化的位置、大小與是否為新發生？")
            if d.domain == "pain":
                qs.append("請確認：疼痛部位、程度與是否影響活動？")
        if not qs:
            qs.append("請確認：是否需要現場評估或於下次巡診提出？")
        return qs[:4]

    def family_notification(self, profile, what_happened, route_text):
        contact = profile.emergency_contacts[0].name if profile.emergency_contacts else "家屬"
        return (
            f"{contact}您好，這裡是機構護理站。{profile.code_name}今天{what_happened}。"
            f"護理師已到場評估，目前安排：{route_text}。我們會持續觀察並再與您聯絡。"
            f"若有問題請回撥護理站。"
        )

    def translate_lines(self, lines_zh, lang):
        from ingest.lexicon import translate_instruction

        return [translate_instruction(line, lang) for line in lines_zh]


# ---------------------------------------------------------------------------
# ChatModelLLM — provider-agnostic, built on settings.get_model() (structured output)
# ---------------------------------------------------------------------------


class _ExtractedDim(BaseModel):
    dimension: str
    value: str | float | None = None
    raw_quote: str = Field(description="exact substring of the caregiver's text")
    direction: str = "unknown"
    confidence: float = 0.7


class _Extraction(BaseModel):
    translation_zh: str | None = None
    domains: list[_ExtractedDim] = Field(default_factory=list)
    seems_different: bool = False
    incident_flags: list[str] = Field(default_factory=list)
    flags: dict[str, bool] = Field(default_factory=dict)
    vitals_reported: dict[str, float | None] = Field(default_factory=dict)
    followups: list[str] = Field(default_factory=list)


EXTRACT_SYSTEM = """你是長照機構的 Intake Agent。照護者用任何語言講一句話，你只做抽取，不做判斷。
規則：
1. 只能填八個維度：intake, elimination, function, cognition, sleep, skin, pain, vitals。
2. 每個維度的 raw_quote 必須是原文的逐字子字串；找不到就不要填。
3. 不改照護者口吻，不加診斷、不加建議、不加嚴重程度。
4. flags 只能是這些布林事實：consciousness_change, new_confusion_or_drowsiness,
   breathing_difficulty, chest_pain, fall_head_strike, cannot_get_up_after_fall,
   no_urine_24h, intake_sudden_drop, fever_feel。
5. incident_flags 只能是 fall, medication_issue, choking, behavior。
6. followups 最多兩題，用照護者的語言，只問缺的事實。
7. translation_zh：非中文時給忠實翻譯。"""


class ChatModelLLM(LLM):
    def __init__(self, model: Any | None = None) -> None:
        s = get_settings()
        self.model = model if model is not None else s.get_model()
        self.name = f"{s.effective_provider}:{s.MODEL_PINNED}"
        self.fallback = MockLLM()

    def extract_observation(self, text, lang, profile=None, baseline=None):
        try:
            de = deidentify(text, profile)
            structured = self.model.with_structured_output(_Extraction)
            res: _Extraction = structured.invoke(
                [("system", EXTRACT_SYSTEM), ("human", f"語言：{lang}\n原話：{de.text}")]
            )
            ts = datetime.now(UTC)
            prov = Provenance(
                source="ai_extracted", author="intake_agent", ts=ts, language_original=lang
            )
            from record_schema import DIMENSIONS, ObservationFlags, Vitals

            domains = {}
            for d in res.domains:
                if d.dimension in DIMENSIONS:
                    domains[d.dimension] = DimensionValue(
                        value=d.value,
                        raw_quote=de.reidentify(d.raw_quote),
                        provenance=prov,
                        confidence=max(0.0, min(1.0, d.confidence)),
                        lang=lang,
                        direction=d.direction
                        if d.direction in ("up", "down", "same")
                        else "unknown",
                    )
            flags = ObservationFlags(
                **{k: v for k, v in res.flags.items() if k in ObservationFlags.model_fields}
            )
            vitals = Vitals(
                **{k: v for k, v in res.vitals_reported.items() if k in Vitals.model_fields}
            )
            obs = StructuredObservation(
                raw_text=text,
                language=lang,
                translation_zh=res.translation_zh,
                domains=domains,
                seems_different=res.seems_different,
                incident_flags=[
                    i
                    for i in res.incident_flags
                    if i in ("fall", "medication_issue", "choking", "behavior")
                ],
                flags=flags,
                vitals_reported=vitals,
                unknown=[d for d in DIMENSIONS if d not in domains],
                followups=[FollowupQA(question=q, lang=lang) for q in res.followups[:2]],
            )
            return _guard_quotes(obs)
        except Exception as e:  # noqa: BLE001
            log.warning("%s extraction failed (%s); using mock", self.name, e)
            return self.fallback.extract_observation(text, lang, profile, baseline)

    def minimal_sbar(self, obs, deltas):
        return self.fallback.minimal_sbar(obs, deltas)

    def draft_isbar(self, profile, baseline, obs, deltas, recent_lines):
        draft = self.fallback.draft_isbar(profile, baseline, obs, deltas, recent_lines)
        try:
            prompt = (
                "你是 Nurse Assist。把以下 ISBAR 草稿的 S 與 B 改寫得更通順，但不得新增事實、"
                '不得加入診斷或處置。只回傳 JSON {"situation":..., "background":...}。\n'
                f"S: {draft.situation}\nB: {draft.background}"
            )

            class _SB(BaseModel):
                situation: str
                background: str

            res: _SB = self.model.with_structured_output(_SB).invoke(prompt)
            draft.situation = scrub_clinical_language(res.situation)
            draft.background = scrub_clinical_language(res.background)
        except Exception as e:  # noqa: BLE001
            log.warning("%s isbar polish failed (%s); keeping mock draft", self.name, e)
        return draft

    def family_notification(self, profile, what_happened, route_text):
        base = self.fallback.family_notification(profile, what_happened, route_text)
        try:
            res = self.model.invoke(
                "把下面這段通知改成更溫暖、白話、不含醫療術語的家屬訊息，長度相近，"
                f"不得新增事實：\n{base}"
            )
            return scrub_clinical_language(str(res.content))
        except Exception as e:  # noqa: BLE001
            log.warning("%s family notification failed (%s)", self.name, e)
            return base

    def translate_lines(self, lines_zh, lang):
        try:

            class _T(BaseModel):
                lines: list[str]

            res: _T = self.model.with_structured_output(_T).invoke(
                f"把以下每一行忠實翻成 {lang}（照服員看得懂的簡單句子），保持行數：\n"
                + "\n".join(lines_zh)
            )
            if len(res.lines) == len(lines_zh):
                return res.lines
        except Exception as e:  # noqa: BLE001
            log.warning("%s translate failed (%s)", self.name, e)
        return self.fallback.translate_lines(lines_zh, lang)


@lru_cache
def get_llm() -> LLM:
    """MockLLM unless a provider AND its key are configured; then ChatModelLLM(get_model())."""
    s = get_settings()
    if s.llm_enabled:
        try:
            return ChatModelLLM(s.get_model())
        except Exception as e:  # noqa: BLE001
            log.warning("%s model unavailable (%s); using MockLLM", s.MODEL_PROVIDER, e)
    return MockLLM()
