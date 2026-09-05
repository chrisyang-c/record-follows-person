from __future__ import annotations

from datetime import date, datetime
from typing import Annotated, Literal, Union

from pydantic import BaseModel, ConfigDict, Field

# ---------------------------------------------------------------------------
# Enums (kept as Literals so they codegen to TS unions)
# ---------------------------------------------------------------------------

Lang = Literal["zh-TW", "id", "vi", "en"]

ProvenanceSource = Literal[
    "caregiver_said",
    "ai_extracted",
    "nurse_assessed",
    "nurse_confirmed",
    "doctor_ordered",
    "system_derived",
]

Dimension = Literal[
    "intake", "elimination", "function", "cognition", "sleep", "skin", "pain", "vitals"
]

DIMENSIONS: tuple[Dimension, ...] = (
    "intake", "elimination", "function", "cognition", "sleep", "skin", "pain", "vitals",
)

DIMENSION_LABELS: dict[str, dict[str, str]] = {
    "intake": {"zh-TW": "進食與飲水", "id": "Makan & minum", "vi": "Ăn uống", "en": "Intake"},
    "elimination": {"zh-TW": "排泄", "id": "Buang air", "vi": "Bài tiết", "en": "Elimination"},
    "function": {"zh-TW": "活動與日常功能", "id": "Aktivitas", "vi": "Vận động", "en": "Function"},
    "cognition": {
        "zh-TW": "意識、認知、情緒、溝通", "id": "Kesadaran & emosi",
        "vi": "Ý thức & cảm xúc", "en": "Cognition",
    },
    "sleep": {"zh-TW": "睡眠", "id": "Tidur", "vi": "Giấc ngủ", "en": "Sleep"},
    "skin": {"zh-TW": "皮膚與傷口", "id": "Kulit & luka", "vi": "Da & vết thương", "en": "Skin"},
    "pain": {"zh-TW": "疼痛", "id": "Nyeri", "vi": "Đau", "en": "Pain"},
    "vitals": {
        "zh-TW": "生命徵象與呼吸症狀", "id": "Tanda vital & napas",
        "vi": "Sinh hiệu & hô hấp", "en": "Vitals",
    },
}

IncidentKind = Literal["fall", "medication_issue", "choking", "behavior"]
Direction = Literal["up", "down", "same", "unknown"]
Status = Literal["draft", "approved"]
Shift = Literal["day", "evening", "night"]
RouteDecision = Literal[
    "contact_contract_hospital", "home_acute_mode_b", "accompany_visit", "observe", "escalate_119"
]


# ---------------------------------------------------------------------------
# Provenance — every line carries one. Never removed, never rewritten.
# ---------------------------------------------------------------------------


class Provenance(BaseModel):
    model_config = ConfigDict(frozen=True)

    source: ProvenanceSource
    author: str
    confirmed_by: str | None = None
    ts: datetime
    language_original: Lang = "zh-TW"


class ProvenanceLine(BaseModel):
    """Append-only ledger row (records/{id}/provenance.jsonl)."""

    line_id: str
    ref: str = Field(description="timeline entry id or document id this line belongs to")
    field: str = Field(default="", description="which field inside the ref, if any")
    source: ProvenanceSource
    author: str
    confirmed_by: str | None = None
    ts: datetime
    language_original: Lang = "zh-TW"


# ---------------------------------------------------------------------------
# Eight dimensions + caregiver observation
# ---------------------------------------------------------------------------


class DimensionValue(BaseModel):
    value: str | float | None = None
    raw_quote: str = Field(description="照護者原話片段")
    provenance: Provenance
    confidence: float = Field(ge=0.0, le=1.0)
    lang: Lang
    direction: Direction = "unknown"


class ObservationFlags(BaseModel):
    """Boolean facts a caregiver can report without instruments.

    Consumed by red_flags/rules.py. These are observations, not diagnoses.
    """

    consciousness_change: bool = False
    new_confusion_or_drowsiness: bool = False
    breathing_difficulty: bool = False
    chest_pain: bool = False
    fall_head_strike: bool = False
    cannot_get_up_after_fall: bool = False
    no_urine_24h: bool = False
    intake_sudden_drop: bool = False
    fever_feel: bool = False


class Vitals(BaseModel):
    temp_c: float | None = None
    sbp: int | None = None
    dbp: int | None = None
    hr: int | None = None
    rr: int | None = None
    spo2: int | None = None
    measured_by: str | None = None
    ts: datetime | None = None


class FollowupQA(BaseModel):
    question: str
    answer: str | None = None
    answered_unknown: bool = False
    lang: Lang = "zh-TW"


class StructuredObservation(BaseModel):
    raw_text: str
    language: Lang
    translation_zh: str | None = None
    domains: dict[str, DimensionValue] = Field(default_factory=dict)
    seems_different: bool = False
    incident_flags: list[IncidentKind] = Field(default_factory=list)
    flags: ObservationFlags = Field(default_factory=ObservationFlags)
    vitals_reported: Vitals | None = None
    unknown: list[Dimension] = Field(default_factory=list)
    followups: list[FollowupQA] = Field(default_factory=list)


class BaselineDelta(BaseModel):
    domain: Dimension
    direction: Direction
    magnitude: float | None = None
    days: int = 1
    note: str = ""
    evidence_refs: list[str] = Field(default_factory=list)


class RedFlagHit(BaseModel):
    rule_id: str
    description: str
    facts: list[str]
    action: Literal["notify_now", "observe"]
    requires_validation: bool = True


class RedFlagResult(BaseModel):
    hits: list[RedFlagHit] = Field(default_factory=list)
    notify_now: bool = False
    observe: bool = False
    disclaimer: str = "需護理師／醫師驗證；非診斷、非檢傷分級。"


# ---------------------------------------------------------------------------
# Profile (FHIR-lite: Patient / Condition / AllergyIntolerance / MedicationStatement)
# ---------------------------------------------------------------------------


class Condition(BaseModel):
    display: str
    code: str | None = None
    onset: date | None = None


class AllergyIntolerance(BaseModel):
    substance: str
    reaction: str | None = None
    severity: Literal["mild", "moderate", "severe"] | None = None


class MedicationStatement(BaseModel):
    name: str
    dose: str
    schedule: str
    is_anticoagulant: bool = False
    started: date | None = None
    ordered_by: str | None = None


class Contact(BaseModel):
    name: str
    relation: str
    phone: str
    line_user_id: str | None = None
    notify_first: bool = False


class Facility(BaseModel):
    name: str
    phone: str
    contract_type: str = "特約醫療機構"


HEALTH_ID_PATTERN = r"^P-\d{7}$"


class Profile(BaseModel):
    patient_id: str
    health_id: str = Field(
        default="P-0000000",
        pattern=HEALTH_ID_PATTERN,
        description="Personal Health ID（P-0000000）：紀錄屬於本人、跟著人一輩子；機構是場域之一",
    )
    code_name: str = Field(description="代號，非真名")
    sex: Literal["M", "F"]
    birth_year: int
    room: str
    conditions: list[Condition] = Field(default_factory=list)
    allergies: list[AllergyIntolerance] = Field(default_factory=list)
    medications: list[MedicationStatement] = Field(default_factory=list)
    dnr: bool = False
    emergency_contacts: list[Contact] = Field(default_factory=list)
    contract_facility: Facility
    current_location: Literal["facility", "home", "hospital"] = "facility"
    caregiver_code_name: str
    caregiver_language: Lang = "zh-TW"
    primary_nurse: str
    one_liner: str = Field(default="", description="一句話的人")
    height_cm: float | None = None
    weight_kg: float | None = Field(default=None, description="最近一次量的體重（本人 wellness 區用）")

    @property
    def on_anticoagulant(self) -> bool:
        return any(m.is_anticoagulant for m in self.medications)


# ---------------------------------------------------------------------------
# Care Circle — who may see which part of this person's record (patient-owned access)
# ---------------------------------------------------------------------------

CareRole = Literal["patient", "family", "caregiver", "nurse", "doctor"]
Scope = Literal["who", "timeline", "docs", "talk"]


class CareCircleMember(BaseModel):
    health_id: str
    member_id: str = Field(description="身份代號（cg_xiaofang、nurse_lin、fam_P001、P001…）")
    name: str = ""
    role: CareRole
    scopes: list[Scope] = Field(default_factory=list, description="可見範圍：who|timeline|docs|talk 子集")
    valid_from: datetime
    valid_to: datetime | None = None
    granted_by: str = Field(description="誰授權（本人或代理）")
    purpose: str = Field(default="", description="WHY：為了什麼看（VISION §16；授權時必填）")
    revoked_at: datetime | None = None

    def active(self, now: datetime | None = None) -> bool:
        from datetime import UTC as _UTC
        from datetime import datetime as _dt

        now = now or _dt.now(_UTC)
        if self.revoked_at is not None:
            return False
        if self.valid_from > now:
            return False
        return self.valid_to is None or self.valid_to > now


class AccessLogEntry(BaseModel):
    health_id: str
    who: str
    role: CareRole | None = None
    what: str = Field(description="看了什麼（who|timeline|docs|talk|summary|ask…）")
    purpose: str = Field(default="", description="WHY：為了什麼看（依授權的 purpose 帶入）")
    ts: datetime


# ---------------------------------------------------------------------------
# Channel 4 — sensor events (simulated wearable). The event layer records「可能跌倒」, never「跌倒」.
# Raw values are nurse-only; caregiver and doctor views carry no confidence or percentages.
# ---------------------------------------------------------------------------

VerifyChoice = Literal["with_patient", "fine", "maybe_injured", "unreachable"]
VERIFY_LABELS: dict[str, str] = {
    "with_patient": "我在他身邊",
    "fine": "他沒事",
    "maybe_injured": "他可能受傷",
    "unreachable": "聯絡不上",
}


class SensorVerification(BaseModel):
    choice: VerifyChoice
    text: str = ""
    by: str
    ts: datetime


class SensorEvent(BaseModel):
    id: str
    health_id: str
    patient_id: str
    ts: datetime
    kind: Literal["possible_fall"] = "possible_fall"
    location: str = ""
    accel_peak_g: float = Field(description="加速度尖峰（g）")
    orientation_change_deg: float = Field(description="姿態改變（度）")
    still_seconds: int = Field(description="事件後靜止秒數")
    hr_before: int
    hr_after: int
    spo2_after: int | None = None
    status: Literal["pending", "verified", "closed"] = "pending"
    hard_flag: bool = Field(default=False, description="紅燈硬條件命中（靜止 ≥ N 秒或 SpO₂ 低於門檻）")
    hard_facts: list[str] = Field(default_factory=list)
    verification: SensorVerification | None = None
    thread_id: str | None = Field(default=None, description="Path A thread（若已通知護理師）")
    source: str = "simulated_wearable"


# ---------------------------------------------------------------------------
# Baseline — updated only via ◇nurse_confirm_baseline → baseline_write
# ---------------------------------------------------------------------------


class BaselineEntry(BaseModel):
    dimension: Dimension
    value: str | float | None = None
    description: str
    valid_from: date
    valid_to: date | None = None
    set_by: ProvenanceSource
    confirmed_by: str | None = None
    provenance: Provenance


class Baseline(BaseModel):
    entries: list[BaselineEntry] = Field(default_factory=list)
    vitals_usual: Vitals | None = None

    def current(self, dimension: str, on: date | None = None) -> BaselineEntry | None:
        on = on or date.today()
        candidates = [
            e
            for e in self.entries
            if e.dimension == dimension
            and e.valid_from <= on
            and (e.valid_to is None or e.valid_to >= on)
        ]
        if not candidates:
            return None
        return sorted(candidates, key=lambda e: e.valid_from)[-1]


class BaselineProposal(BaseModel):
    patient_id: str
    proposals: list[BaselineEntry]
    reason: str
    status: Status = "draft"
    proposed_by: ProvenanceSource = "system_derived"
    confirmed_by: str | None = None
    source_order_id: str | None = None


VitalMetric = Literal["temp_c", "sbp", "dbp", "hr", "rr", "spo2"]

VITAL_LABELS: dict[str, str] = {
    "temp_c": "體溫",
    "sbp": "收縮壓",
    "dbp": "舒張壓",
    "hr": "心率",
    "rr": "呼吸",
    "spo2": "血氧",
}

VITAL_UNITS: dict[str, str] = {
    "temp_c": "°C",
    "sbp": "mmHg",
    "dbp": "mmHg",
    "hr": "／分",
    "rr": "／分",
    "spo2": "%",
}


class VitalsBand(BaseModel):
    """這個人自己的正常範圍，從 timeline 的量測值算出來，不是族群常模。

    `vitals_usual` 是護理師寫的一組數字；這裡是從實際量測算出來的「帶」。
    兩者並存：帶只用來說明「這次跟他平常比起來如何」，
    要更新 `vitals_usual` 仍必須走 ◇nurse_confirm_baseline（CLAUDE.md §1.6）。

    `established=False` 時不得用來判斷任何事情——樣本太少的「正常範圍」
    是誤報的主要來源，不是靈敏度不夠。
    """

    metric: VitalMetric
    label: str
    unit: str
    center: float = Field(description="中位數（不是平均數：生理值有離群值）")
    spread: float = Field(description="中位數絕對偏差 MAD（不是標準差）")
    low: float = Field(description="第 10 百分位")
    high: float = Field(description="第 90 百分位")
    n: int = Field(description="樣本數")
    days: int = Field(description="涵蓋幾天")
    established: bool
    reason: str = Field(default="", description="established=False 時說明為什麼")
    text: str = Field(default="", description="給人看的一行，例如「收縮壓 129–139 mmHg」")


class VitalsBands(BaseModel):
    """一位住民的所有生理值正常帶。系統推導，不寫入 baseline。"""

    patient_id: str
    computed_at: datetime
    window_days: int
    bands: dict[str, VitalsBand] = Field(default_factory=dict)

    def get(self, metric: str) -> VitalsBand | None:
        band = self.bands.get(metric)
        return band if band is not None and band.established else None


# ---------------------------------------------------------------------------
# Timeline — append only: Observation | Incident | Encounter | Order
# ---------------------------------------------------------------------------


class MinimalSBAR(BaseModel):
    s: str = Field(description="一行 S：現況（引用照護者）")
    a_change_vs_baseline: str = Field(description="一行 A：只寫與基線比的變化")
    status: Status = "draft"
    author: Literal["ai", "nurse"] = "ai"
    confirmed_by: str | None = None
    nurse_edit: str | None = None


class TimelineBase(BaseModel):
    id: str
    patient_id: str
    ts: datetime
    status: Status = "draft"
    confirmed_by: str | None = None
    provenance: Provenance
    related_ids: list[str] = Field(default_factory=list)


class Observation(TimelineBase):
    kind: Literal["observation"] = "observation"
    shift: Shift
    observation: StructuredObservation
    deltas: list[BaselineDelta] = Field(default_factory=list)
    minimal_sbar: MinimalSBAR | None = None
    vitals: Vitals | None = None
    red_flags: RedFlagResult | None = None


class Incident(TimelineBase):
    kind: Literal["incident"] = "incident"
    incident_kind: IncidentKind | Literal["acute"]
    summary: str
    incident_file_id: str | None = None


LifeEventType = Literal["condition", "hospitalization", "surgery", "fall", "other"]


class LifeEvent(TimelineBase):
    """終身時間軸的大事件（年層只顯示這些＋事故）：疾病確診、住院、手術、跌倒。
    來自出院摘要／病歷匯入（demo 為 seed），provenance 記來源機構。"""

    kind: Literal["life_event"] = "life_event"
    event_type: LifeEventType
    title: str
    summary: str = ""
    facility: str = ""
    ended: date | None = None


class WearableDaily(TimelineBase):
    """通道 4 穿戴每日指標（模擬）。只有事實數值，不存任何品質分數；照護鏈只把心率／SpO₂ 當觀察事實。
    資料形狀參考 health-ref 的 daily_metrics（想法，重新設計）。"""

    kind: Literal["wearable_daily"] = "wearable_daily"
    day: date
    steps: int
    exercise_min: int
    resting_hr: int
    hrv_ms: int
    spo2: int
    sleep_hours: float
    deep_sleep_hours: float
    rem_hours: float
    source: str = "simulated_wearable"


class Encounter(TimelineBase):
    kind: Literal["encounter"] = "encounter"
    encounter_type: Literal["round", "emergency", "visit"]
    doctor: str
    summary: str
    order_ids: list[str] = Field(default_factory=list)


class OrderItem(BaseModel):
    text: str
    category: Literal["medication", "observation", "diet", "activity", "referral", "other"]
    target_dimension: Dimension | None = None
    caregiver_instruction: str | None = None


class OrderFollowUp(BaseModel):
    done: bool | None = None
    effective: bool | None = None
    note: str = ""
    evidence_refs: list[str] = Field(default_factory=list)


class Order(TimelineBase):
    kind: Literal["order"] = "order"
    doctor: str
    raw_text: str
    items: list[OrderItem] = Field(default_factory=list)
    encounter_id: str | None = None
    caregiver_notes_doc_id: str | None = None
    follow_up: OrderFollowUp | None = None


TimelineEntry = Annotated[
    Union[Observation, Incident, Encounter, Order, LifeEvent, WearableDaily],
    Field(discriminator="kind"),
]


# ---------------------------------------------------------------------------
# Documents — RoundPage | HandoffPage | VisitPage | IncidentFile | CaregiverNotes
# ---------------------------------------------------------------------------


class ISBAR(BaseModel):
    identity: str
    situation: str
    background: str
    ai_change_vs_baseline: str = Field(description="AI 的 A：只寫與基線比的變化")
    ai_questions_for_nurse: list[str] = Field(
        default_factory=list, description="AI 的 R：只寫請確認事項（提問式）"
    )
    nurse_assessment: str | None = Field(default=None, description="A — 只有護理師寫")
    nurse_recommendation: str | None = Field(default=None, description="R — 只有護理師寫")
    status: Status = "draft"
    author: Literal["ai", "nurse"] = "ai"
    confirmed_by: str | None = None
    confirmed_at: datetime | None = None


class OnsiteAssessment(BaseModel):
    vitals: Vitals
    consciousness: str
    wound: str | None = None
    notes: str | None = None
    assessed_by: str
    ts: datetime


class CaregiverSection(BaseModel):
    raw_text: str
    language: Lang
    translation_zh: str | None = None
    domains: dict[str, DimensionValue] = Field(default_factory=dict)
    seems_different: bool = False
    incident_flags: list[IncidentKind] = Field(default_factory=list)
    followups: list[FollowupQA] = Field(default_factory=list)
    unknown: list[Dimension] = Field(default_factory=list)
    image_summary: str | None = None
    caregiver_confirmed_meaning: bool | None = None
    provenance: Provenance


class NurseSection(BaseModel):
    onsite_assessment: OnsiteAssessment | None = None
    isbar: ISBAR
    confirmed_by: str | None = None
    confirmed_at: datetime | None = None


class Notification(BaseModel):
    to: Literal["family", "hospital", "119", "nurse", "second_nurse", "head_nurse"]
    channel: Literal["line", "phone", "screen"]
    content: str
    status: Literal["draft", "approved", "sent", "displayed_only"] = "draft"
    sent_at: datetime | None = None
    approved_by: str | None = None
    content_ref: str | None = None


class FollowUp(BaseModel):
    due_at: datetime
    question: str
    answer: str | None = None
    answered_at: datetime | None = None
    set_by: str


class DocBase(BaseModel):
    id: str
    patient_id: str
    generated_at: datetime
    generated_from: list[str] = Field(default_factory=list, description="timeline ids")
    status: Status = "draft"
    author: str
    confirmed_by: str | None = None
    provenance: Provenance
    audience: Literal["doctor", "er", "nurse", "caregiver", "family", "system"]


class IncidentFile(DocBase):
    doc_type: Literal["incident_file"] = "incident_file"
    caregiver_section: CaregiverSection
    nurse_section: NurseSection
    red_flags: RedFlagResult | None = None
    route_decision: RouteDecision | None = None
    notifications: list[Notification] = Field(default_factory=list)
    follow_up: FollowUp | None = None
    sensor_event: SensorEvent | None = Field(default=None, description="通道 4：觸發此事件的感測事件（含照護者四鍵驗證）")


class HandoffPage(DocBase):
    doc_type: Literal["handoff_page"] = "handoff_page"
    variant: Literal["phone_isbar", "visit_page"]
    what_happened: str
    usual_state: list[str]
    medications: list[str]
    dnr: bool
    contacts: list[str]
    isbar_text: str


class VisitPage(DocBase):
    doc_type: Literal["visit_page"] = "visit_page"
    reason: str
    recent: list[str]
    medications: list[str]


class TrendPoint(BaseModel):
    date: date
    value: float | None = None
    label: str = ""


class TrendSeries(BaseModel):
    dimension: Dimension
    points: list[TrendPoint]


class TrendLine(BaseModel):
    dimension: Dimension
    direction: Direction
    summary: str
    window_days: int
    magnitude: float | None = None
    evidence_refs: list[str] = Field(default_factory=list)
    is_abnormal: bool = False


class TrendReport(BaseModel):
    patient_id: str
    since: date
    until: date
    lines: list[TrendLine]
    cross_dimension_signal: str | None = None
    series: list[TrendSeries] = Field(default_factory=list)
    incident_ids: list[str] = Field(default_factory=list)
    generated_by: ProvenanceSource = "system_derived"


class OrderFollowUpLine(BaseModel):
    order_id: str
    text: str
    done: bool | None = None
    effective: bool | None = None
    note: str = ""


class RoundPage(DocBase):
    doc_type: Literal["round_page"] = "round_page"
    who: str = Field(description="① 一句話的人＋基線")
    baseline_summary: list[str] = Field(default_factory=list)
    changes: list[TrendLine] = Field(default_factory=list, description="② 異常優先")
    cross_dimension_signal: str | None = None
    order_followup: list[OrderFollowUpLine] = Field(default_factory=list, description="③")
    questions: list[str] = Field(default_factory=list, description="④ 提問式")
    chart: list[TrendSeries] = Field(default_factory=list, description="變化最大的兩個維度")
    since: date
    page_limit_ok: bool = True
    agent_note: str = Field(default="", description="由哪個 subagent 產生、呼叫了哪些工具幾次")


class CaregiverNotes(DocBase):
    doc_type: Literal["caregiver_notes"] = "caregiver_notes"
    lang: Lang
    items: list[str] = Field(description="本月注意三件事")
    items_zh: list[str] = Field(default_factory=list)
    source_order_id: str


Document = Annotated[
    Union[IncidentFile, HandoffPage, VisitPage, RoundPage, CaregiverNotes],
    Field(discriminator="doc_type"),
]


# ---------------------------------------------------------------------------
# PersonRecord — one per person, follows the person
# ---------------------------------------------------------------------------


class PersonRecord(BaseModel):
    profile: Profile
    baseline: Baseline
    timeline: list[TimelineEntry] = Field(default_factory=list)
    documents: list[Document] = Field(default_factory=list)
    provenance: list[ProvenanceLine] = Field(default_factory=list)


__all__ = [
    "Lang", "ProvenanceSource", "Dimension", "DIMENSIONS", "DIMENSION_LABELS", "IncidentKind",
    "Direction", "Status", "Shift", "RouteDecision", "Provenance", "ProvenanceLine",
    "DimensionValue", "ObservationFlags", "Vitals", "FollowupQA", "StructuredObservation",
    "BaselineDelta", "RedFlagHit", "RedFlagResult", "Condition", "AllergyIntolerance",
    "MedicationStatement", "Contact", "Facility", "Profile", "HEALTH_ID_PATTERN", "CareRole",
    "Scope", "CareCircleMember", "AccessLogEntry", "VerifyChoice", "VERIFY_LABELS",
    "SensorVerification", "SensorEvent", "BaselineEntry", "Baseline",
    "BaselineProposal", "VitalMetric", "VITAL_LABELS", "VITAL_UNITS", "VitalsBand", "VitalsBands",
    "MinimalSBAR", "TimelineBase", "Observation", "Incident", "Encounter",
    "LifeEventType", "LifeEvent", "WearableDaily",
    "OrderItem", "OrderFollowUp", "Order", "TimelineEntry", "ISBAR", "OnsiteAssessment",
    "CaregiverSection", "NurseSection", "Notification", "FollowUp", "DocBase", "IncidentFile",
    "HandoffPage", "VisitPage", "TrendPoint", "TrendSeries", "TrendLine", "TrendReport",
    "OrderFollowUpLine", "RoundPage", "CaregiverNotes", "Document", "PersonRecord",
]
