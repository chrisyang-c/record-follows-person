"""All LLM calls live here. Nothing else in apps/api may import langchain/anthropic.

Two implementations behind one interface:
  * MockLLM      — deterministic keyword extraction / templating. No network. Used when
                   MODEL_PROVIDER=mock, by tests, eval and CI, and whenever the provider key
                   is missing.
  * ChatModelLLM — any LangChain chat model from settings.get_model() (ChatOpenAI when
                   MODEL_PROVIDER=openai, ChatAnthropic when anthropic), pinned to MODEL_PINNED,
                   temperature=0. NEVER falls back: a failed or missing model raises
                   LLMUnavailable, which the API turns into a visible error (HTTP 503).
  MockLLM is a *test double* for pytest/CI only (MODEL_PROVIDER=mock); its question planner
  raises LLMUnavailable so no rule-based questions can ever reach a user.

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

from pydantic import BaseModel, Field, field_validator
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
from core.trace import timed, trace
from ingest.lexicon import extract_with_lexicon

log = logging.getLogger(__name__)


class LLMUnavailable(RuntimeError):
    """No model configured, or the model call failed. Surface it; do not fall back to rules."""


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

    def next_question(self, ctx: dict[str, Any]) -> NextQuestionOut:
        """Decide the next follow-up (what to ask, how, and why). Raises LLMUnavailable."""
        raise NotImplementedError

    def caregiver_notes(self, order_text: str, profile: Profile) -> list[str]:
        """Order Ingest Agent: turn an order into ≤3 everyday-language things for the caregiver."""
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

    def next_question(self, ctx):
        raise LLMUnavailable("MODEL_PROVIDER=mock：沒有模型，不產生追問（不退回規則版）")

    def caregiver_notes(self, order_text, profile):  # test double
        from ingest.doctor_order import caregiver_notes_zh, parse_order

        return caregiver_notes_zh(parse_order(order_text))


def invoke_with_backoff(fn: Any, *args: Any, attempts: int = 4, **kwargs: Any) -> Any:
    """Provider 429 (TPM) → wait what the provider asks for, then retry (traced)."""
    import re
    import time

    for i in range(attempts):
        try:
            return fn(*args, **kwargs)
        except Exception as e:  # noqa: BLE001
            msg = str(e)
            if ("429" not in msg and "rate limit" not in msg.lower()) or i == attempts - 1:
                raise
            m = re.search(r"try again in ([\d.]+)\s*(ms|s)", msg)
            wait = float(m.group(1)) / (1000 if m and m.group(2) == "ms" else 1) if m else 15.0
            wait = min(max(wait + 1.5, 3.0), 65.0)
            trace("llm.rate_limited", attempt=i + 1, wait_s=wait, error=msg[:160])
            time.sleep(wait)
    raise RuntimeError("unreachable")


class _Structured:
    def __init__(self, runnable: Any) -> None:
        self.runnable = runnable

    def invoke(self, *args: Any, **kwargs: Any) -> Any:
        return invoke_with_backoff(self.runnable.invoke, *args, **kwargs)


def _structured(model: Any, schema: type[BaseModel]) -> Any:
    """Structured output that tolerates optional fields: OpenAI's default json_schema mode
    rejects schemas with defaults, so use tool/function calling on every provider."""
    try:
        return _Structured(model.with_structured_output(schema, method="function_calling"))
    except TypeError:  # provider without a `method` kwarg
        return _Structured(model.with_structured_output(schema))


# ---------------------------------------------------------------------------
# ChatModelLLM — provider-agnostic, built on settings.get_model() (structured output)
# ---------------------------------------------------------------------------


def record_prefix(profile: Profile | None, baseline: Baseline | None, days: int = 14) -> str:
    """The resident's record as one fixed block: profile, baseline, last ``days`` days of timeline.

    Prompt caching: this block is appended to the (fixed) system prompt and does not change
    between turns of the same day, so every later call reuses the cached prefix. Only the turn
    state (what was said / asked) comes after it. Never put timestamps or per-turn data here."""
    if profile is None:
        return "（無住民紀錄）"
    from datetime import UTC, datetime, timedelta

    from record_schema import DIMENSION_LABELS

    from record.store import get_store

    label = lambda d: DIMENSION_LABELS[d]["zh-TW"]  # noqa: E731
    age = datetime.now(UTC).year - profile.birth_year
    meds = "、".join(
        f"{m.name} {m.dose} {m.schedule}{'（抗凝血）' if m.is_anticoagulant else ''}"
        for m in profile.medications
    )
    lines = [
        f"住民：{profile.code_name}，{age} 歲，{profile.room}；"
        f"慢性病：{'、'.join(c.display for c in profile.conditions) or '無'}；"
        f"過敏：{'、'.join(a.substance for a in profile.allergies) or '無'}；用藥：{meds or '無'}；"
        f"DNR：{'是' if profile.dnr else '否'}。{profile.one_liner}",
    ]
    if baseline is not None:
        lines.append(
            "基線（平常）："
            + "；".join(
                f"{label(e.dimension)}：{e.description}"
                for e in baseline.entries
                if e.valid_to is None
            )
        )
    store = get_store()
    if store.exists(profile.patient_id):
        since = datetime.now(UTC).date() - timedelta(days=days)
        rows = []
        for e in store.load_timeline(profile.patient_id, since=since):
            day = e.ts.astimezone().strftime("%m/%d")
            if e.kind == "observation":
                dims = "、".join(
                    f"{label(k)}「{v.raw_quote}」({v.direction})"
                    for k, v in e.observation.domains.items()
                )
                rows.append(f"{day} 觀察：{dims or e.observation.raw_text[:40]}")
            elif e.kind == "incident":
                rows.append(f"{day} 事故：{e.summary[:60]}")
            elif e.kind == "order":
                rows.append(f"{day} 醫囑：{e.raw_text[:80]}")
            elif e.kind == "encounter":
                rows.append(f"{day} 巡診：{e.summary[:60]}")
        if rows:
            lines.append(f"timeline（近 {days} 天，只增不改）：\n" + "\n".join(rows))
    return "\n".join(lines)


RECORD_SEP = "\n\n住民紀錄（固定，一天內不變）：\n"


def _system_with_record(system: str, profile: Profile | None, baseline: Baseline | None) -> str:
    """system prompt + the resident's record as ONE system message.

    Probed 2026-09-05 on gpt-5.6-luna: the prompt cache is only served when the stable prefix
    is inside the system message; a short system followed by a fixed user message never hits
    (0 cached tokens on identical requests). So the record block lives here, not in a human
    message, and the per-turn state is the only human message."""
    return system + RECORD_SEP + record_prefix(profile, baseline)


def _cfg(kind: str) -> dict[str, Any]:
    """Tag a call so core.usage can attribute tokens / cost to it."""
    return {"tags": [kind]}


class NextQuestionOut(BaseModel):
    ask: bool = Field(description="還需要再問一題嗎？夠了就 false")
    dimension: str | None = Field(
        default=None, description="這題主要在補哪個維度（八維度 key），紅燈關鍵事實可為 null"
    )
    question: str = Field(default="", description="一句日常口語的問題，對照護者說")
    reason: str = Field(default="", description="為什麼問這題（存進 trace，給護理師看）")


class ISBARDraftOut(BaseModel):
    situation: str
    background: str
    change_vs_baseline: str = Field(description="只寫與基線比的變化")
    questions_for_nurse: list[str] = Field(description="只寫請護理師確認的事，問句")


class MinimalOut(BaseModel):
    s: str
    a_change_vs_baseline: str


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

    @field_validator("vitals_reported", mode="before")
    @classmethod
    def _numbers_only(cls, v: Any) -> dict[str, float | None]:
        """The model sometimes puts words in a number slot（「呼吸很快」）: keep the number
        or drop the value — the wording still lands in the vitals dimension's raw_quote."""
        if not isinstance(v, dict):
            return {}
        out: dict[str, float | None] = {}
        for k, x in v.items():
            if x is None or isinstance(x, (int, float)):
                out[k] = None if x is None else float(x)
            else:
                try:
                    out[k] = float(str(x).strip())
                except ValueError:
                    out[k] = None
        return out


EXTRACT_SYSTEM = """你是長照機構的 Intake Agent。
照護者講一句話，你只做「抽取」，不判斷、不推論、不補充。

八個維度（只有原文字面上提到對應內容才可以填）：
- intake 進食與飲水：吃多少、喝多少、體重、吞嚥（例：「只吃一半」「水喝很少」「喝水嗆到」）
- elimination 排泄：大便、尿、便秘、拉肚子、失禁、尿布
- function 活動與日常功能：走路、站、轉位、需要人扶、比較沒力（「跌倒」本身不算 function）
- cognition 意識、認知、情緒、溝通：混亂、嗜睡、一直睡、叫不醒、反應慢、
   認不得人、講話變少、不講話、情緒
- sleep 睡眠：夜間醒來幾次、睡不著、日夜顛倒（「一直睡／嗜睡」是 cognition，不是 sleep）
- skin 皮膚與傷口：紅、破皮、壓瘡、腫、水腫、瘀青
- pain 疼痛：痛、喊痛、不舒服（含部位）
- vitals 生命徵象與呼吸症狀：咳、痰、喘、發燒、燙、體溫、血壓、心跳、血氧、呼吸快

direction：down＝比平常少或變差、up＝比平常多或新出現、same＝跟平常一樣、unknown＝有提到但看不出方向。
value：intake 用比例（吃完 1.0、一半 0.5、幾口 0.2、都沒吃 0）；sleep 用夜間醒來次數；其他可空。

規則：
1. 一個維度只在原文有對應字詞時才填；沒提到就不填。不要因為「跌倒」就推論 function 或 pain。
2. 照護者的猜測、問句、診斷用語（「應該是感冒了吧」「是不是中風」「可以吃止痛藥嗎」「肺炎」）
   不是觀察：這種句子 domains 全空、flags 全 false、incident_flags 空。
3. raw_quote 必須是原文逐字子字串（複製原文片段，不改字）。
4. flags 只在原文字面出現對應事實時才 true：
   consciousness_change（叫不醒／叫不太醒／意識不清／沒反應）、
   new_confusion_or_drowsiness（混亂／胡言亂語／認不得／嗜睡／一直睡）、
   breathing_difficulty（喘／呼吸困難／呼吸很快）、chest_pain（胸痛／胸口悶／胸口痛）、
   fall_head_strike（撞到頭／頭撞到）、cannot_get_up_after_fall（爬不起來／站不起來）、
   no_urine_24h（整天沒尿／尿布是乾的）、intake_sudden_drop（一口都沒吃／都不吃）、
   fever_feel（發燒／燙）。
5. incident_flags 只能是 fall（跌倒／摔倒）、medication_issue（拒藥／吐藥／不肯吃藥／漏藥）、
   choking（嗆到）、behavior（打人／遊走／想跑出去）。
6. vitals_reported 只填原文出現的數字：temp_c、sbp、dbp、hr、rr、spo2。
7. seems_different 只在原文有「跟平常不一樣／怪怪的／不太對／不像平常」時 true。
8. followups 最多兩題，只問缺的事實，用照護者的日常口語；translation_zh 只在原文不是中文時填。

範例：
「王伯這三天飯只吃一半，晚上起來三次」→ intake(0.5, down, "飯只吃一半")、
  sleep(3, up, "晚上起來三次")
「他應該是感冒了吧」→ domains {}、flags 全 false
「剛剛在浴室跌倒，撞到頭，自己爬不起來」→ domains {}；
  flags fall_head_strike、cannot_get_up_after_fall；incident_flags [fall]
「喝水嗆到，咳了很久」→ intake("喝水嗆到")、vitals("咳了很久")；incident_flags [choking]
「早上的藥吐出來了，不肯再吃」→ domains {}；incident_flags [medication_issue]
「跟平常不一樣，說不上來哪裡怪」→ domains {}；seems_different true
「晚上起來三次，白天嗜睡」→ sleep(3, up, "晚上起來三次")、cognition(null, up, "白天嗜睡")；
  flags new_confusion_or_drowsiness"""


class ChatModelLLM(LLM):
    def __init__(self, model: Any | None = None) -> None:
        s = get_settings()
        self.model = model if model is not None else s.get_model()
        self.name = f"{s.effective_provider}:{s.MODEL_PINNED}"
        self.fallback = MockLLM()

    def extract_observation(self, text, lang, profile=None, baseline=None):
        try:
            de = deidentify(text, profile)
            structured = _structured(self.model, _Extraction)
            with timed() as tm:
                res: _Extraction = structured.invoke(
                    [
                        ("system", _system_with_record(EXTRACT_SYSTEM, profile, baseline)),
                        ("human", f"語言：{lang}\n原話：{de.text}"),
                    ],
                    _cfg("llm.extract"),
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
            trace(
                "llm.extract",
                provider=self.name,
                input=de.text,
                output={
                    "domains": {
                        d.dimension: [d.value, d.direction, d.raw_quote] for d in res.domains
                    },
                    "flags": [k for k, v in res.flags.items() if v],
                    "incident_flags": res.incident_flags,
                    "seems_different": res.seems_different,
                    "vitals_reported": {
                        k: v for k, v in res.vitals_reported.items() if v is not None
                    },
                    "followups": res.followups[:2],
                },
                duration_ms=tm.ms,
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
            trace("llm.extract", provider=self.name, input=text, error=str(e))
            raise LLMUnavailable(f"模型抽取失敗（{self.name}）：{e}") from e

    def minimal_sbar(self, obs, deltas):
        base = self.fallback.minimal_sbar(obs, deltas)
        prompt = (
            f"原話：{obs.raw_text}\n"
            "抽取："
            + "; ".join(f"{k}={dv.raw_quote}({dv.direction})" for k, dv in obs.domains.items())
            + "\n"
            f"與基線比：{'; '.join(_delta_text(d) for d in deltas) or '無明顯變化'}"
        )
        try:
            with timed() as tm:
                res: MinimalOut = _structured(self.model, MinimalOut).invoke(
                    [("system", MINIMAL_SYSTEM), ("human", prompt)], _cfg("llm.minimal_sbar")
                )
            s = scrub_clinical_language(res.s.strip()) or base.s
            a = (
                scrub_clinical_language(res.a_change_vs_baseline.strip())
                or base.a_change_vs_baseline
            )
            trace(
                "llm.minimal_sbar",
                provider=self.name,
                input=prompt,
                output={"s": s, "a": a},
                duration_ms=tm.ms,
            )
            return MinimalSBAR(s=s, a_change_vs_baseline=a, status="draft", author="ai")
        except Exception as e:  # noqa: BLE001
            trace("llm.minimal_sbar", provider=self.name, error=str(e))
            raise LLMUnavailable(f"模型草擬 SBAR 失敗（{self.name}）：{e}") from e

    def draft_isbar(self, profile, baseline, obs, deltas, recent_lines):
        draft = self.fallback.draft_isbar(profile, baseline, obs, deltas, recent_lines)
        answers = "; ".join(f"{q.question}→{q.answer or '不知道'}" for q in obs.followups) or "無"
        flags = [k for k, v in obs.flags.model_dump().items() if v] + list(obs.incident_flags)
        prompt = (
            f"I：{draft.identity}\nS（事實）：{draft.situation}\nB（事實）：{draft.background}\n"
            f"與基線比（規則計算）：{'; '.join(_delta_text(d) for d in deltas) or '無明顯變化'}\n"
            f"照護者追問回答：{answers}\n紅燈／事件旗標：{flags}"
        )
        try:
            with timed() as tm:
                res: ISBARDraftOut = _structured(self.model, ISBARDraftOut).invoke(
                    [
                        ("system", _system_with_record(ISBAR_SYSTEM, profile, baseline)),
                        ("human", prompt),
                    ],
                    _cfg("llm.draft_isbar"),
                )
            qs = [scrub_clinical_language(q.strip()) for q in res.questions_for_nurse if q.strip()]
            qs = [q if q.endswith("？") else q.rstrip("?。") + "？" for q in qs[:4]]
            draft.situation = scrub_clinical_language(res.situation.strip()) or draft.situation
            draft.background = scrub_clinical_language(res.background.strip()) or draft.background
            draft.ai_change_vs_baseline = (
                scrub_clinical_language(res.change_vs_baseline.strip())
                or draft.ai_change_vs_baseline
            )
            draft.ai_questions_for_nurse = qs or draft.ai_questions_for_nurse
            trace(
                "llm.draft_isbar",
                provider=self.name,
                input=prompt,
                output={
                    "situation": draft.situation,
                    "background": draft.background,
                    "ai_change_vs_baseline": draft.ai_change_vs_baseline,
                    "ai_questions_for_nurse": draft.ai_questions_for_nurse,
                },
                duration_ms=tm.ms,
            )
        except Exception as e:  # noqa: BLE001
            trace("llm.draft_isbar", provider=self.name, error=str(e))
            raise LLMUnavailable(f"模型草擬 ISBAR 失敗（{self.name}）：{e}") from e
        return draft

    def family_notification(self, profile, what_happened, route_text):
        base = self.fallback.family_notification(profile, what_happened, route_text)
        try:
            prompt = base
            with timed() as tm:
                res = invoke_with_backoff(
                    self.model.invoke,
                    [("system", FAMILY_SYSTEM), ("human", prompt)],
                    _cfg("llm.family_notification"),
                )
            out = scrub_clinical_language(str(res.content))
            trace(
                "llm.family_notification",
                provider=self.name,
                input=prompt,
                output=out,
                duration_ms=tm.ms,
            )
            return out
        except Exception as e:  # noqa: BLE001
            trace("llm.family_notification", provider=self.name, error=str(e))
            raise LLMUnavailable(f"模型草擬家屬通知失敗（{self.name}）：{e}") from e

    def translate_lines(self, lines_zh, lang):
        try:

            class _T(BaseModel):
                lines: list[str]

            res: _T = _structured(self.model, _T).invoke(
                f"把以下每一行忠實翻成 {lang}（照服員看得懂的簡單句子），保持行數：\n"
                + "\n".join(lines_zh)
            )
            if len(res.lines) == len(lines_zh):
                return res.lines
        except Exception as e:  # noqa: BLE001
            raise LLMUnavailable(f"模型翻譯失敗（{self.name}）：{e}") from e
        raise LLMUnavailable("模型翻譯行數不符")


MINIMAL_SYSTEM = (
    "你是 Nurse Assist。用照護者的原話寫一行 S（現況）、一行 A（只寫與基線比的變化）。"
    "不得新增事實、不得診斷、不得建議處置，各 ≤ 60 字。"
)
ISBAR_SYSTEM = (
    "你是 Nurse Assist，預填 ISBAR 草稿給護理師審核。規則：S 引用照護者原話與追問回答；"
    "B 用 profile 與基線；change_vs_baseline 只寫「與基線比的變化」（不下判斷）；"
    "questions_for_nurse 只寫請護理師現場確認的事，每條是問句、以「？」結尾，最多 4 條。"
    "不得出現診斷詞、治療建議、檢傷等級。各段 ≤ 120 字。"
)
FAMILY_SYSTEM = (
    "把使用者給的這段通知改成更溫暖、白話、不含醫療術語的家屬訊息，長度相近，不得新增事實。"
)
NOTES_SYSTEM = (
    "你是 Order Ingest Agent。把醫師醫囑翻成照服員這個月要注意的三件事（最多 3 句，"
    "每句 ≤ 30 字，日常口語、可執行、只講照服員做得到的觀察與記錄，不改藥、不下診斷）。"
)


NEXT_Q_SYSTEM = """你是長照機構的 Intake Agent，正在用聊天跟照服員確認一位住民今天的狀況，
   一次只問一題。
你每一輪都會拿到：這個人的 profile 與基線、八個維度目前哪些已知／未知、已經問過的題目、
   規則層的紅燈判定。
你要決定：還要不要問（ask）、問哪個維度或哪個關鍵事實（dimension）、怎麼問（question）、
   為什麼（reason）。

原則：
1. 一次只問一題，用台灣日常口語對照服員說（≤ 30 字），像「王伯今天有喝水嗎？大概幾杯？」，
   不用醫療術語、不用表單語。
2. 已知的維度不要再問；已問過的題目不要重複。
3. 依這個人的慢性病、用藥與基線決定優先順序（COPD→呼吸咳嗽、失智→精神反應、
   抗凝血劑→跌倒後的頭部／瘀青、
   壓傷→皮膚、糖尿病→進食飲水），並考慮已知觀察之間的關聯（吃得少→問喝水、大小便）。
4. phase=red（規則層已通知護理師）：改問護理師到場前最需要的關鍵事實（例：跌倒→怎麼跌、
   哪裡痛、能不能自己站、
   清不清醒、有沒有流血；發燒或意識改變→從何時開始、現在叫得醒嗎、有沒有喘），一題一件事，
   dimension 可為 null。
5. 預算用完、或八維度與關鍵事實已足夠，就 ask=false。
6. 不下診斷、不建議處置、不安撫過頭。reason 一句話，給護理師看。"""


def _next_question_impl(self: ChatModelLLM, ctx: dict[str, Any]) -> NextQuestionOut:
    # message order is fixed for prompt caching: system → 住民紀錄 (unchanged all day) → this turn
    record = ctx.get("record") or f"住民：{ctx.get('profile')}\n基線（平常）：{ctx.get('baseline')}"
    prompt = (
        f"phase：{ctx.get('phase')}\n"
        f"照服員第一句：{ctx.get('said')}\n已知維度：{ctx.get('known') or '無'}\n"
        f"未知維度：{ctx.get('unknown')}\n事件／紅燈事實：{ctx.get('facts') or '無'}\n"
        f"已問過（問→答）：{ctx.get('asked') or '無'}\n剩餘追問預算：{ctx.get('budget')} 題"
        + (f"\n注意：{ctx['note']}" if ctx.get("note") else "")
    )
    try:
        with timed() as tm:
            res: NextQuestionOut = _structured(self.model, NextQuestionOut).invoke(
                [
                    ("system", NEXT_Q_SYSTEM + RECORD_SEP + record),
                    ("human", prompt),
                ],
                _cfg("llm.next_question"),
            )
        res.question = scrub_clinical_language(res.question.strip())
        trace(
            "llm.next_question",
            provider=self.name,
            input=prompt,
            output={"ask": res.ask, "dimension": res.dimension, "question": res.question},
            reason=res.reason,
            duration_ms=tm.ms,
        )
        return res
    except Exception as e:  # noqa: BLE001
        trace("llm.next_question", provider=self.name, input=prompt, error=str(e))
        raise LLMUnavailable(f"模型決定追問失敗（{self.name}）：{e}") from e


class _NotesOut(BaseModel):
    items: list[str] = Field(description="1–3 句，照服員看得懂、做得到的事")


def _caregiver_notes_impl(self: ChatModelLLM, order_text: str, profile: Profile) -> list[str]:
    prompt = (
        f"住民：{profile.code_name}，"
        f"{'、'.join(c.display for c in profile.conditions)}\n醫囑：{order_text}"
    )
    try:
        with timed() as tm:
            res: _NotesOut = _structured(self.model, _NotesOut).invoke(
                [("system", NOTES_SYSTEM), ("human", prompt)], _cfg("llm.caregiver_notes")
            )
        items = [scrub_clinical_language(x.strip()) for x in res.items if x.strip()][:3]
        trace(
            "llm.caregiver_notes", provider=self.name, input=prompt, output=items, duration_ms=tm.ms
        )
        if not items:
            raise LLMUnavailable("模型沒有產生注意事項")
        return items
    except LLMUnavailable:
        raise
    except Exception as e:  # noqa: BLE001
        trace("llm.caregiver_notes", provider=self.name, input=prompt, error=str(e))
        raise LLMUnavailable(f"模型產生注意事項失敗（{self.name}）：{e}") from e


ChatModelLLM.next_question = _next_question_impl  # type: ignore[method-assign]
ChatModelLLM.caregiver_notes = _caregiver_notes_impl  # type: ignore[method-assign]


@lru_cache
def get_llm() -> LLM:
    """MockLLM unless a provider AND its key are configured; then ChatModelLLM(get_model())."""
    s = get_settings()
    if s.MODEL_PROVIDER == "mock":
        return MockLLM()  # explicit test double
    if not s.llm_enabled:
        raise LLMUnavailable(f"MODEL_PROVIDER={s.MODEL_PROVIDER} 但沒有 API key（.env）")
    return ChatModelLLM(s.get_model())
