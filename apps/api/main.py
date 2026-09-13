"""FastAPI — the record speaks through here. All graph interaction is start / resume / snapshot."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import Any

from fastapi import FastAPI, Header, HTTPException, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from record_schema import DIMENSION_LABELS, DIMENSIONS, FollowupQA

from agents.personal import AgentDidNotDeliver
from core import policy, security
from core.llm import LLMUnavailable
from core.settings import get_settings
from core.trace import for_ids, tagged
from graphs import registry, runner, worker
from graphs.checkpointer import is_postgres
from ingest import discharge_pdf, doctor_order, fhir_bundle
from ingest import vitals as vitals_ingest
from ingest.caregiver_speech import ingest as ingest_speech
from record import care_circle as cc
from record import conversation as conv
from record import events as sensor_events
from record import followups
from record.store import get_store
from red_flags.rules import RULES, render_lines

log = logging.getLogger("api")


@asynccontextmanager
async def lifespan(app: FastAPI):
    sched = worker.start_scheduler()
    log.info("timeout worker started; checkpointer=%s", "postgres" if is_postgres() else "memory")
    try:
        yield
    finally:
        sched.shutdown(wait=False)


app = FastAPI(title="一份能跟著人走的紀錄 API", version="0.1.0", lifespan=lifespan)


@app.exception_handler(RequestValidationError)
async def _invalid_request(_req, exc: RequestValidationError):
    """Validation responses must not echo passwords or clinical request bodies."""
    from fastapi.responses import JSONResponse

    return JSONResponse(
        status_code=422,
        content={
            "detail": [
                {key: error[key] for key in ("loc", "msg", "type")} for error in exc.errors()
            ]
        },
    )


@app.exception_handler(LLMUnavailable)
async def _llm_unavailable(_req, exc: LLMUnavailable):
    """No model / model call failed → visible error, never a rule fallback."""
    from fastapi.responses import JSONResponse

    return JSONResponse(status_code=503, content={"detail": f"LLM 未設定或呼叫失敗：{exc}"})


@app.exception_handler(AgentDidNotDeliver)
async def _agent_failed(_req, exc: AgentDidNotDeliver):
    from fastapi.responses import JSONResponse

    return JSONResponse(status_code=503, content={"detail": f"agent 沒有產出：{exc}"})


app.add_middleware(policy.PolicyMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in get_settings().AUTH_ALLOWED_ORIGINS.split(",")],
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=True,
)


# --- meta -----------------------------------------------------------------------------------


@app.get("/health")
def health() -> dict[str, Any]:
    s = get_settings()
    return {
        "ok": True,
        "model_provider": s.MODEL_PROVIDER,
        "model_pinned": s.MODEL_PINNED,
        "llm_enabled": s.llm_enabled,
        "effective_provider": s.effective_provider,
        "checkpointer": "postgres" if is_postgres() else "memory",
        "time": datetime.now(UTC).isoformat(),
    }


@app.get("/meta/dimensions")
def dimensions() -> dict[str, Any]:
    return {"dimensions": list(DIMENSIONS), "labels": DIMENSION_LABELS}


@app.get("/meta/red-flags")
def red_flags_meta() -> list[dict[str, Any]]:
    return [
        {
            "id": r.id,
            "description": r.description,
            "action": r.action,
            "requires_validation": r.requires_validation,
        }
        for r in RULES
    ]


# --- records --------------------------------------------------------------------------------


@app.get("/residents")
def residents() -> list[dict[str, Any]]:
    store = get_store()
    # Directory permission does not expose timeline counts, assignment details or events.
    return [
        {
            k: getattr(store.load_profile(pid), k)
            for k in ("patient_id", "health_id", "code_name", "room")
        }
        for pid in policy.visible_patients({"who"})
    ]


def _resident_row(store: Any, pid: str) -> dict[str, Any]:
    p = store.load_profile(pid)
    tl = store.load_timeline(pid)
    return {
        "patient_id": pid,
        "code_name": p.code_name,
        "room": p.room,
        "caregiver_language": p.caregiver_language,
        "caregiver_code_name": p.caregiver_code_name,
        "primary_nurse": p.primary_nurse,
        "timeline_count": len(tl),
        "last_entry_ts": tl[-1].ts.isoformat() if tl else None,
        "incident_count": sum(1 for e in tl if e.kind == "incident"),
    }


def _home_card(store: Any, pid: str, role: str) -> dict[str, Any]:
    """What one resident card on a role home page needs — computed here so the page is one call
    (KNOWN_ISSUES #19: was /residents + one /summary, /trends or /round-pages per resident)."""
    from datetime import date, timedelta

    if role == "caregiver":
        msgs = conv.messages(pid)
        today = date.today().isoformat()
        s = conv.session(pid)
        notes = next((d.items for d in reversed(store.load_documents(pid, "caregiver_notes"))), [])
        profile = store.load_profile(pid)
        obs = store.load_timeline(pid, kinds={"observation"})
        latest = obs[-1] if obs else None
        changed = [
            d.domain for d in (latest.deltas if latest else []) if d.direction in ("up", "down")
        ]
        pending_ev = sensor_events.pending(pid)
        red_threads = [
            row
            for row in registry.list_threads(status="interrupted")
            if row.get("patient_id") == pid and row.get("graph") == "path_a"
        ]
        alerts: list[str] = []
        if pending_ev:
            alerts.append("感測器：可能跌倒，請確認他的狀況")
        if s and s.phase == "red":
            alerts.append("護理師已收到通知")
        elif red_threads:
            alerts.append("護理師正在處理一件事")
        events = [
            _event_row(e)
            for e in sorted(
                [e for e in store.load_timeline(pid) if e.kind in MAJOR_KINDS],
                key=lambda e: e.ts,
                reverse=True,
            )[:3]
        ]
        return {
            "recorded_today": any(m.role == "caregiver" and m.ts[:10] == today for m in msgs)
            or any(e.ts.date().isoformat() == today for e in obs),
            "notes_count": len(notes),
            "session_phase": s.phase if s and s.phase != "closed" else None,
            "status_line": (
                "護理師正在處理一件事"
                if alerts and "護理師" in alerts[-1]
                else ("今天有幾項跟平常不一樣" if changed else "跟平常差不多")
            ),
            "changed_dimensions": changed,
            "latest_ts": latest.ts.isoformat() if latest else None,
            "pending_event": sensor_events.public_view(pending_ev) if pending_ev else None,
            "alerts": alerts,
            "recent_events": events,
            "care_team": {
                "primary_nurse": profile.primary_nurse,
                "doctor": "dr_wu",
                "facility": profile.contract_facility.model_dump(mode="json"),
                "emergency_contacts": [
                    c.model_dump(mode="json") for c in profile.emergency_contacts
                ],
            },
        }
    if role == "doctor":
        pages = store.load_documents(pid, "round_page")
        if not pages:
            return {"round_page": None}
        pg = pages[-1]
        return {
            "round_page": {
                "first": (pg.changes[0].summary if pg.changes else "本期八維度皆與基線一致"),
                "generated_at": pg.generated_at.isoformat()
                if hasattr(pg.generated_at, "isoformat")
                else pg.generated_at,
                "status": pg.status,
                "confirmed_by": pg.confirmed_by,
            }
        }
    # nurse: abnormal trend lines + the series of (at most) the first two abnormal dimensions
    from agents.subagents import trend_analyzer

    until = datetime.now(UTC).date()
    since = until - timedelta(days=14)
    obs = store.load_timeline(pid, since=since, kinds={"observation"})
    inc = [e.id for e in store.load_timeline(pid, since=since, kinds={"incident"})]
    rep = trend_analyzer.analyze(pid, obs, inc, since, until, 7)  # type: ignore[arg-type]
    abnormal = [line for line in rep.lines if line.is_abnormal]
    dims = {line.dimension for line in abnormal[:2]}
    with_v = [o for o in obs if o.vitals is not None]
    band = _band_summary(
        pid, with_v[-1].vitals if with_v else None, [o.vitals for o in with_v[-4:-1]]
    )
    return {
        "abnormal": [line.model_dump(mode="json") for line in abnormal],
        "series": [s.model_dump(mode="json") for s in rep.series if s.dimension in dims],
        # RF13：偏離他自己平常的量測範圍（observe，不是紅燈）
        "vitals_departures": band["departures"],
        "vitals_band_texts": [b["text"] for b in band["bands"]],
    }


@app.get("/home/{role}")
def home(role: str) -> dict[str, Any]:
    """Role home page in one call: every resident + the card data that role shows."""
    role = role.lower()
    if role not in ("caregiver", "nurse", "doctor"):
        raise HTTPException(404, "unknown role")
    store = get_store()
    return {
        "role": role,
        "generated_at": datetime.now(UTC).isoformat(),
        "residents": [
            {**_resident_row(store, pid), "card": _home_card(store, pid, role)}
            for pid in policy.visible_patients(
                {"who", "timeline", "docs"} if role == "doctor" else policy.ALL
            )
        ],
    }


# --- 通道 4：模擬跌倒訊號 --------------------------------------------------------------------


class SimFallIn(BaseModel):
    still_seconds: int | None = None
    spo2_after: int | None = None
    location: str = "房間"


def _pid_of_health_id(health_id: str) -> str:
    store = get_store()
    for pid in store.list_patients():
        if store.load_profile(pid).health_id == health_id:
            return pid
    raise HTTPException(404, "unknown health_id")


@app.post("/sim/fall/{health_id}")
def sim_fall(health_id: str, body: SimFallIn | None = None) -> dict[str, Any]:
    """Simulated wearable signal → the event layer records「可能跌倒」(not「跌倒」).
    Hard conditions (still ≥60 s or SpO₂ <92, RF11) notify the nurse at once via Path A;
    otherwise the caregiver is asked to verify (four buttons in talk). Returns the nurse view."""
    from record_schema import StructuredObservation

    from red_flags.rules import RedFlagInput, evaluate

    body = body or SimFallIn()
    pid = _pid_of_health_id(health_id)
    store = get_store()
    profile = store.load_profile(pid)
    ev = vitals_ingest.simulate_fall(
        pid,
        health_id,
        still_seconds=body.still_seconds,
        spo2_after=body.spo2_after,
        location=body.location,
    )
    rf = evaluate(
        RedFlagInput(observation=StructuredObservation(raw_text="", language="zh-TW"), sensor=ev)
    )
    ev.hard_flag = rf.notify_now
    ev.hard_facts = [f for h in rf.hits for f in h.facts]
    sensor_events.create(pid, ev)
    s = conv.open_session(pid)
    when = ev.ts.astimezone().strftime("%H:%M")
    if rf.notify_now:
        snap = runner.start(
            "path_a",
            pid,
            {
                "path": "incident",
                "raw_input": {
                    "turns": [
                        {
                            "text": f"感測器偵測到{profile.code_name}可能跌倒"
                            f"（{when}，{ev.location}）"
                        }
                    ],
                    "language": "zh-TW",
                    "caregiver_id": "sensor",
                    "dialog_id": s.dialog_id,
                    "sensor_event": ev.model_dump(mode="json"),
                },
            },
        )
        ev.thread_id = snap["thread_id"]
        ev.status = "verified" if ev.verification else "pending"
        sensor_events.update(pid, ev)
        s.thread_id, s.phase, s.pending_event_id = snap["thread_id"], "red", ev.id
        conv.save_session(pid, s)
        conv.append(
            pid,
            "system",
            f"感測器偵測到{profile.code_name}可能於 {when} 跌倒（{ev.location}）。"
            "已通知護理師，請留在他身邊。",
            s.session_id,
            kind="event",
            meta={"sensor_event_id": ev.id, "red": True, "thread_id": snap["thread_id"]},
            author="red_flag_rules",
        )
    else:
        s.pending_event_id = ev.id
        conv.save_session(pid, s)
        conv.append(
            pid,
            "system",
            f"感測器偵測到{profile.code_name}可能於 {when} 跌倒（{ev.location}）。請確認他的狀況。",
            s.session_id,
            kind="event",
            meta={"sensor_event_id": ev.id, "needs_verification": True},
            author="sensor",
        )
    return {
        "event": sensor_events.nurse_view(ev),
        "notified_nurse": rf.notify_now,
        "patient_id": pid,
    }


class VerifyIn(BaseModel):
    choice: str
    text: str = ""


# --- 01 活體數位孿生（本人 wellness 視角；docs/UIUX_OMNI_TWIN.md §4.1）--------------

# 一句 wellness 建議（只在 01 與 /me 允許；來源標「一般建議」，不是醫療建議）
WELLNESS_TIP: dict[str, str] = {
    "intake": "三餐固定時間、少量多餐，白天分次喝水。",
    "elimination": "每天固定時間如廁，蔬果與水分足夠。",
    "function": "每天走一走、站一站，動作慢一點但不要不動。",
    "cognition": "白天多說話、多曬太陽，晚上少刺激。",
    "sleep": "固定上床時間，睡前少喝水、少看螢幕。",
    "skin": "翻身、保持乾爽，皮膚乾就擦乳液。",
    "pain": "痛就說，記下部位與時間，別硬撐。",
    "vitals": "有喘、咳、發燒的感覺就先休息並讓人知道。",
}


@app.get("/twin/{patient_id}")
def twin(patient_id: str, x_who: str | None = Header(default=None)) -> dict[str, Any]:
    """01 activity body map: per dimension — state (same / changed / red), today's words and
    value, days changed, baseline, 14-day series, latest caregiver quote, a general wellness tip.
    Wellness voice is allowed here only (CLAUDE.md §1.9)."""
    from datetime import timedelta

    from agents.subagents import trend_analyzer

    store = get_store()
    if not store.exists(patient_id):
        raise HTTPException(404, "unknown patient")
    role, _tabs = _authorize(patient_id, x_who, "patient")
    cc.log_access(patient_id, x_who, role, "twin")  # type: ignore[arg-type]
    profile = store.load_profile(patient_id)
    baseline = store.load_baseline(patient_id)
    until = datetime.now(UTC).date()
    since = until - timedelta(days=14)
    obs = store.load_timeline(patient_id, since=since, kinds={"observation"})
    rep = trend_analyzer.analyze(patient_id, obs, [], since, until, baseline=baseline)  # type: ignore[arg-type]
    series = {s.dimension: [p.model_dump(mode="json") for p in s.points] for s in rep.series}
    trend_abnormal = {line.dimension: line for line in rep.lines if line.is_abnormal}
    latest = obs[-1] if obs else None
    deltas = {d.domain: d for d in (latest.deltas if latest else [])}
    red_now = bool(latest and latest.red_flags and latest.red_flags.notify_now) or any(
        row.get("patient_id") == patient_id and row.get("graph") == "path_a"
        for row in registry.list_threads(status="interrupted")
    )
    base = {e.dimension: e for e in baseline.entries if e.valid_to is None}
    dims: dict[str, Any] = {}
    for d in DIMENSIONS:
        dv = latest.observation.domains.get(d) if latest else None
        if dv is None:  # last mention within 14 days
            for e in reversed(obs):
                if d in e.observation.domains:
                    dv = e.observation.domains[d]
                    break
        delta = deltas.get(d)
        trend = trend_abnormal.get(d)
        changed = bool(delta and delta.direction in ("up", "down")) or trend is not None
        state = "red" if (red_now and changed) else ("changed" if changed else "same")
        dims[d] = {
            "label": DIMENSION_LABELS[d]["zh-TW"],
            "state": state,
            "quote": dv.raw_quote if dv else None,
            "value": dv.value if dv else None,
            "direction": delta.direction
            if delta and delta.direction != "same"
            else (trend.direction if trend else (dv.direction if dv else "unknown")),
            "days": delta.days if delta else (trend.window_days if trend else 0),
            "note": delta.note if delta and delta.note else (trend.summary if trend else ""),
            "baseline": base[d].description if d in base else "",
            "series": series.get(d, []),
            "tip": WELLNESS_TIP[d],
        }
    with_v = [o for o in obs if o.vitals is not None]
    band = _band_summary(
        patient_id, with_v[-1].vitals if with_v else None, [o.vitals for o in with_v[-4:-1]]
    )
    if band["established"]:
        dims["vitals"]["baseline"] = "他平常：" + "；".join(b["text"] for b in band["bands"])
        if band["departures"]:
            dims["vitals"]["note"] = "；".join(band["departures"])
            if dims["vitals"]["state"] == "same":
                dims["vitals"]["state"] = "changed"
    changed_n = sum(1 for v in dims.values() if v["state"] != "same")
    # channel 4 wearable daily metrics (facts only) + the avatar's state（本人 wellness 區）
    wear = store.load_timeline(patient_id, since=since, kinds={"wearable_daily"})
    wear_rows = [
        {
            "day": w.day.isoformat(),
            "steps": w.steps,
            "exercise_min": w.exercise_min,
            "resting_hr": w.resting_hr,
            "hrv_ms": w.hrv_ms,
            "spo2": w.spo2,
            "sleep_hours": w.sleep_hours,
            "deep_sleep_hours": w.deep_sleep_hours,
            "rem_hours": w.rem_hours,
        }
        for w in wear
    ]
    last_w = wear_rows[-1] if wear_rows else None
    mood = "attention" if red_now else ("changed" if changed_n else "same")
    return {
        "profile": {
            "code_name": profile.code_name,
            "health_id": profile.health_id,
            "birth_year": profile.birth_year,
            "height_cm": profile.height_cm,
            "weight_kg": profile.weight_kg,
        },
        "wearable": wear_rows,
        "vitals_bands": band,
        "avatar": {
            "sleep_hours": last_w["sleep_hours"] if last_w else None,
            "weight_kg": profile.weight_kg,
            "height_cm": profile.height_cm,
            "mood": mood,
        },
        "today_ts": latest.ts.isoformat() if latest else None,
        "status_line": "護理師正在處理一件事"
        if red_now
        else (f"今天有 {changed_n} 項跟平常不一樣" if changed_n else "跟平常差不多"),
        "dimensions": dims,
    }


# --- 個人生理值正常帶（apps/api/baseline）：只描述「跟他自己平常比」，不寫回 baseline ---------


def _band_summary(pid: str, latest_vitals: Any | None, recent_vitals: list[Any]) -> dict[str, Any]:
    """Established bands as one-line texts, plus RF13-style departure sentences for the latest
    measured vitals. No z-score, no percentage (CLAUDE.md §1.8)."""
    from baseline import departure
    from baseline.loader import bands_for

    vb = bands_for(pid)
    if vb is None:
        return {"bands": [], "departures": [], "established": False}
    bands = [b.model_dump(mode="json") for b in vb.bands.values() if b.established]
    departures: list[str] = []
    if latest_vitals is not None:
        for b in vb.bands.values():
            val = getattr(latest_vitals, b.metric, None)
            if val is None:
                continue
            recent = [
                getattr(v, b.metric)
                for v in recent_vitals
                if getattr(v, b.metric, None) is not None
            ]
            line = departure(b, float(val), recent=[float(r) for r in recent[-3:]])
            if line:
                departures.append(line)
    return {"bands": bands, "departures": departures, "established": bool(bands)}


@app.get("/patients/{patient_id}/vitals-bands")
def patient_vitals_bands(
    patient_id: str, x_who: str | None = Header(default=None)
) -> dict[str, Any]:
    """護理師端：這個人自己的量測範圍（p10–p90）與最近一次量測是否偏離。"""
    store = get_store()
    if not store.exists(patient_id):
        raise HTTPException(404, "unknown patient")
    role, _tabs = _authorize(patient_id, x_who, "nurse")
    cc.log_access(patient_id, x_who, role, "vitals-bands")  # type: ignore[arg-type]
    obs = store.load_timeline(patient_id, kinds={"observation"})
    with_v = [o for o in obs if o.vitals is not None]
    latest = with_v[-1].vitals if with_v else None
    return _band_summary(patient_id, latest, [o.vitals for o in with_v[-4:-1]])


# --- 本人 App（第四扇門）：/me ----------------------------------------------------------------

MAJOR_KINDS = {"life_event", "incident"}


@app.get("/me/{patient_id}/home")
def me_home(patient_id: str, x_who: str | None = Header(default=None)) -> dict[str, Any]:
    """Patient homepage (VISION §28.1): status line, today's 8 dimensions, lifelong summary,
    recent events. No confidence values, no scores."""
    from datetime import date

    store = get_store()
    if not store.exists(patient_id):
        raise HTTPException(404, "unknown patient")
    role, tabs = _authorize(patient_id, x_who, "patient")
    cc.log_access(patient_id, x_who, role, "me:home")  # type: ignore[arg-type]
    profile = store.load_profile(patient_id)
    tl = store.load_timeline(patient_id)
    obs = [e for e in tl if e.kind == "observation"]
    latest = obs[-1] if obs else None
    today_dims = (
        {
            k: {"raw_quote": v.raw_quote, "direction": v.direction, "value": v.value}
            for k, v in latest.observation.domains.items()
        }
        if latest
        else {}
    )
    changed = [d.domain for d in (latest.deltas if latest else []) if d.direction in ("up", "down")]
    red = bool(latest and latest.red_flags and latest.red_flags.notify_now)
    status_line = (
        "護理師正在處理一件事" if red else ("今天有幾項跟平常不一樣" if changed else "跟平常差不多")
    )
    life = [e for e in tl if e.kind == "life_event"]
    first_year = min((e.ts.year for e in tl), default=date.today().year)
    events = sorted([e for e in tl if e.kind in MAJOR_KINDS], key=lambda e: e.ts, reverse=True)[:5]
    return {
        "profile": profile.model_dump(mode="json"),
        "status_line": status_line,
        "today": {
            "ts": latest.ts.isoformat() if latest else None,
            "dimensions": today_dims,
            "vitals": latest.vitals.model_dump(mode="json") if latest and latest.vitals else None,
            "changed_dimensions": changed,
        },
        "lifelong": {
            "conditions": len(profile.conditions),
            "hospitalizations": sum(1 for e in life if e.event_type == "hospitalization"),
            "surgeries": sum(1 for e in life if e.event_type == "surgery"),
            "falls": sum(1 for e in life if e.event_type == "fall")
            + sum(1 for e in tl if e.kind == "incident" and e.incident_kind == "fall"),
            "years_of_records": date.today().year - first_year,
            "since": first_year,
        },
        "recent_events": [_event_row(e) for e in events],
        "allowed_tabs": tabs,
    }


INCIDENT_ZH = {
    "fall": "跌倒",
    "medication_issue": "拒藥／吐藥",
    "choking": "嗆咳",
    "behavior": "攻擊／遊走",
    "acute": "急症",
}


def _event_row(e: Any) -> dict[str, Any]:
    if e.kind == "life_event":
        return {
            "id": e.id,
            "ts": e.ts.isoformat(),
            "type": e.event_type,
            "title": e.title,
            "summary": e.summary,
            "facility": e.facility,
        }
    quote = e.summary.split("「", 1)[1].split("」", 1)[0] if "「" in e.summary else ""
    return {
        "id": e.id,
        "ts": e.ts.isoformat(),
        "type": e.incident_kind,
        "title": f"{INCIDENT_ZH.get(e.incident_kind, '事件')}（機構內）"
        + (f"：「{quote}」" if quote else ""),
        "summary": e.summary,
        "facility": "",
    }


@app.get("/me/{patient_id}/timeline")
def me_timeline(patient_id: str, x_who: str | None = Header(default=None)) -> dict[str, Any]:
    """Year → month → event. The year layer only carries major events (conditions, hospital
    stays, surgeries, falls); observations sit inside their month."""
    store = get_store()
    if not store.exists(patient_id):
        raise HTTPException(404, "unknown patient")
    role, tabs = _authorize(patient_id, x_who, "patient")
    if "timeline" not in tabs:
        raise HTTPException(403, "未獲授權")
    cc.log_access(patient_id, x_who, role, "me:timeline")  # type: ignore[arg-type]
    years: dict[int, dict[str, Any]] = {}
    for e in store.load_timeline(patient_id):
        y = years.setdefault(e.ts.year, {"year": e.ts.year, "major": [], "months": {}})
        if e.kind in MAJOR_KINDS:
            y["major"].append(_event_row(e))
        m = y["months"].setdefault(e.ts.month, {"month": e.ts.month, "count": 0, "events": []})
        m["count"] += 1
        if e.kind in MAJOR_KINDS or e.kind in ("encounter", "order"):
            m["events"].append(
                _event_row(e)
                if e.kind in MAJOR_KINDS
                else {
                    "id": e.id,
                    "ts": e.ts.isoformat(),
                    "type": e.kind,
                    "title": ("巡診：" if e.kind == "encounter" else "醫囑：")
                    + (e.summary if e.kind == "encounter" else e.raw_text)[:40],
                    "summary": "",
                    "facility": "",
                }
            )
    out = []
    for y in sorted(years.values(), key=lambda x: -x["year"]):
        y["months"] = sorted(y["months"].values(), key=lambda m: -m["month"])
        out.append(y)
    return {"years": out}


class AskIn(BaseModel):
    question: str


@app.post("/me/{patient_id}/ask")
def me_ask(
    patient_id: str, body: AskIn, x_who: str | None = Header(default=None)
) -> dict[str, Any]:
    """「問我的紀錄」：the person's own agent retrieves from timeline + documents and answers
    only with sentences that cite record lines; nothing found → says so. No advice."""
    from agents.personal import ask_record

    store = get_store()
    if not store.exists(patient_id):
        raise HTTPException(404, "unknown patient")
    role, tabs = _authorize(patient_id, x_who, "patient")
    if "timeline" not in tabs:
        raise HTTPException(403, "未獲授權")
    if not body.question.strip():
        raise HTTPException(400, "empty question")
    cc.log_access(patient_id, x_who, role, "me:ask")  # type: ignore[arg-type]
    answer, meta = ask_record(patient_id, body.question.strip(), who=x_who)
    return {"question": body.question.strip(), **answer, "meta": meta}


@app.get("/records/{patient_id}")
def record(patient_id: str) -> dict[str, Any]:
    store = get_store()
    if not store.exists(patient_id):
        raise HTTPException(404, "unknown patient")
    return store.load(patient_id).model_dump(mode="json")


@app.get("/records/{patient_id}/timeline")
def timeline(
    patient_id: str, since: str | None = None, kind: str | None = None
) -> list[dict[str, Any]]:
    store = get_store()
    if not store.exists(patient_id):
        raise HTTPException(404, "unknown patient")
    s = datetime.fromisoformat(since) if since else None
    return [
        e.model_dump(mode="json")
        for e in store.load_timeline(patient_id, since=s, kinds={kind} if kind else None)
    ]


@app.get("/records/{patient_id}/documents")
def documents(patient_id: str, doc_type: str | None = None) -> list[dict[str, Any]]:
    store = get_store()
    if not store.exists(patient_id):
        raise HTTPException(404, "unknown patient")
    return [
        d.model_dump(mode="json")
        for d in store.load_documents(patient_id, doc_type)
        if policy.document_visible(d.doc_type)
    ]


@app.get("/records/{patient_id}/documents/{doc_id}")
def document(patient_id: str, doc_id: str) -> dict[str, Any]:
    d = get_store().get_document(patient_id, doc_id)
    if d is None:
        raise HTTPException(404, "unknown document")
    if not policy.document_visible(d.doc_type):
        raise HTTPException(403, "未獲授權：文件類型")
    return d.model_dump(mode="json")


@app.get("/records/{patient_id}/provenance")
def provenance(patient_id: str) -> list[dict[str, Any]]:
    return [line.model_dump(mode="json") for line in get_store().read_provenance(patient_id)]


@app.get("/records/{patient_id}/follow-ups")
def follow_up_tasks(patient_id: str, status: str | None = None) -> list[dict[str, Any]]:
    return [task.model_dump(mode="json") for task in followups.list_tasks(patient_id, status)]


class FollowUpAnswerIn(BaseModel):
    answer: str | None = Field(default=None, max_length=2000)


@app.post("/records/{patient_id}/follow-ups/{task_id}/ack")
def acknowledge_follow_up(patient_id: str, task_id: str, body: FollowUpAnswerIn) -> dict[str, Any]:
    try:
        task = followups.acknowledge(task_id, patient_id=patient_id, answer=body.answer)
    except KeyError as exc:
        raise HTTPException(404, "unknown follow-up task") from exc
    return task.model_dump(mode="json")


@app.get("/round-pages/{patient_id}")
def latest_round_page(patient_id: str) -> dict[str, Any]:
    pages = get_store().load_documents(patient_id, "round_page")
    if not pages:
        raise HTTPException(404, "no published RoundPage yet — run the round flow")
    return pages[-1].model_dump(mode="json")


@app.get("/caregiver-notes/{patient_id}")
def latest_caregiver_notes(patient_id: str) -> dict[str, Any]:
    notes = get_store().load_documents(patient_id, "caregiver_notes")
    if not notes:
        raise HTTPException(404, "no caregiver notes yet — enter an order in the round flow")
    return notes[-1].model_dump(mode="json")


class RoundStartIn(BaseModel):
    round_date: str | None = None


# --- patient page: one load for who / timeline / docs / talk ---------------------------------


def _pending_for(patient_id: str) -> list[dict[str, Any]]:
    items = []
    for row in registry.list_threads(status="interrupted"):
        if row.get("patient_id") != patient_id:
            continue
        snap = runner.snapshot(row["thread_id"])
        vals = snap["values"]
        items.append(
            {
                "thread_id": row["thread_id"],
                "graph": snap["graph"],
                "interrupt_type": (snap["interrupt"] or {}).get("type"),
                "red_flag": bool((vals.get("red_flags") or {}).get("notify_now")),
                "red_flag_lines": render_lines(
                    __import__("record_schema").RedFlagResult.model_validate(vals["red_flags"])
                )
                if vals.get("red_flags")
                else [],
                "minimal_sbar": vals.get("minimal_sbar"),
                "sbar": vals.get("sbar"),
                "caregiver_reports": (vals.get("caregiver_reports") or [])[-5:],
                "deadline": vals.get("deadline"),
                "escalation_level": vals.get("escalation_level", 0),
                "updated_at": vals.get("updated_at"),
            }
        )
    return items


def _authorize(
    patient_id: str, who: str | None, x_role: str | None = None
) -> tuple[str, list[str]]:
    """HTTP uses only the verified session; direct domain callers must provide an identity."""
    if policy.actor.get():
        it = policy.current()
        policy.require(patient_id)
        return it["role"], policy.effective_scopes(patient_id)
    if who:
        identity = cc.whoami(who)
        scopes = cc.scopes_for(patient_id, who, cc.ROLE_PURPOSE.get((identity or {}).get("role")))
        if not scopes:
            raise HTTPException(403, "未獲授權：你不在這個人的 Care Circle 裡")
        role = cc.role_of(patient_id, who) or "caregiver"
        return role, list(scopes)
    raise HTTPException(401, "需要已驗證的個人登入")


class LoginIn(BaseModel):
    who: str
    patient_id: str | None = None
    password: str = Field(min_length=1, max_length=1024)
    purpose: str | None = None


@app.post("/login")
def login(body: LoginIn, request: Request, response: Response) -> dict[str, Any]:
    """Authenticate one provisioned person. Login never grants or restores consent."""
    peer = request.client.host if request.client else "unknown"
    try:
        identity = security.authenticate(body.who, body.password, peer)
    except security.AuthenticationRateLimited as exc:
        raise HTTPException(
            429, "登入嘗試過多，請稍後再試", headers={"Retry-After": str(exc.retry_after)}
        ) from None
    if not identity:
        raise HTTPException(401, "帳號或密碼不正確")
    purpose = body.purpose or cc.ROLE_PURPOSE[identity["role"]]
    if purpose not in cc.PURPOSES:
        raise HTTPException(400, "invalid purpose")
    pid = body.patient_id or identity.get("patient_id")
    if identity["role"] == "patient":
        pid = pid or body.who
    candidate = {**identity, "purpose": purpose}
    if pid and not policy.effective_scopes(pid, candidate):
        security.audit(
            pid,
            body.who,
            "login",
            outcome="denied",
            purpose=purpose,
            details={"reason": "no_active_grant_for_purpose"},
        )
        raise HTTPException(403, "未獲授權：登入不會恢復或新增授權")
    security.revoke_session(request.cookies.get("rfp_session", ""))
    session = security.create_session(body.who, purpose, pid)
    cookie_options = {
        "secure": get_settings().AUTH_COOKIE_SECURE,
        "samesite": "lax",
        "path": "/",
        "max_age": 8 * 3600,
    }
    response.set_cookie("rfp_session", session.pop("token"), httponly=True, **cookie_options)
    response.set_cookie("rfp_csrf", session["csrf_token"], httponly=False, **cookie_options)
    security.audit(pid, body.who, "login", outcome="allowed", purpose=purpose)
    return session


@app.get("/auth/session")
def auth_session() -> dict[str, Any]:
    return policy.current()


@app.post("/auth/logout")
def auth_logout(request: Request, response: Response) -> dict[str, bool]:
    security.revoke_session(request.cookies.get("rfp_session", ""))
    response.delete_cookie("rfp_session", path="/")
    response.delete_cookie("rfp_csrf", path="/")
    return {"ok": True}


@app.get("/whoami")
def whoami(me: str | None = None) -> dict[str, Any]:
    """Deprecated alias: never look up arbitrary identities from a query parameter."""
    it = policy.current()
    if me and me != it["who"]:
        raise HTTPException(403, "未獲授權")
    return it


@app.get("/patients/{patient_id}/summary")
def patient_summary(
    patient_id: str,
    tab: str | None = None,
    x_role: str | None = Header(default=None),
    x_who: str | None = Header(default=None),
) -> dict[str, Any]:
    """One response, projected on the server by resource scope and verified role."""
    from datetime import date, timedelta

    from agents.subagents import trend_analyzer

    store = get_store()
    if not store.exists(patient_id):
        raise HTTPException(404, "unknown patient")
    role, allowed_tabs = _authorize(patient_id, x_who, x_role)
    if tab and tab not in allowed_tabs:
        raise HTTPException(403, "未獲授權：沒有此範圍")
    cc.log_access(patient_id, x_who, role, f"summary:{tab}" if tab else "summary")  # type: ignore[arg-type]
    if role in ("patient", "family"):
        role = "caregiver" if role == "family" else "patient"
    profile = store.load_profile(patient_id) if "who" in allowed_tabs else None
    baseline = store.load_baseline(patient_id) if "who" in allowed_tabs else None
    timeline = store.load_timeline(patient_id) if "timeline" in allowed_tabs else []
    if role == "caregiver":
        # Timeline grant covers this person's shared observations, not only one author's.
        timeline = [e for e in timeline if e.kind == "observation"]
    docs = store.load_documents(patient_id) if "docs" in allowed_tabs else []
    docs = [d for d in docs if policy.document_visible(d.doc_type, role)]
    until = datetime.now(UTC).date()
    since = until - timedelta(days=14)
    obs = [e for e in timeline if e.kind == "observation" and e.ts.date() >= since]
    trend = (
        trend_analyzer.analyze(patient_id, obs, [], since, until, baseline=baseline)
        if baseline and "timeline" in allowed_tabs
        else None
    )  # type: ignore[arg-type]
    msgs = conv.messages(patient_id) if "talk" in allowed_tabs else []
    session = conv.session(patient_id) if "talk" in allowed_tabs else None
    full = policy.ALL.issubset(allowed_tabs)
    today = date.today().isoformat()
    return {
        "role": role,
        "patient_id": patient_id,
        "who": x_who,
        "allowed_tabs": allowed_tabs,
        "profile": profile.model_dump(mode="json") if profile else None,
        "baseline": baseline.model_dump(mode="json") if baseline else None,
        "timeline": policy.project([e.model_dump(mode="json") for e in timeline], role),
        "documents": policy.project([d.model_dump(mode="json") for d in docs], role),
        "conversation": policy.project([m.model_dump(mode="json") for m in msgs], role),
        "session": session.model_dump() if session else None,
        "pending": _pending_for(patient_id) if role == "nurse" and full else [],
        "sensor_events": [
            (sensor_events.nurse_view if role == "nurse" else sensor_events.public_view)(e)
            for e in (sensor_events.list_events(patient_id)[-5:] if full else [])
        ],
        "changed_dimensions": [line.dimension for line in trend.lines if line.is_abnormal]
        if trend
        else [],
        "trend_lines": [line.model_dump(mode="json") for line in trend.lines] if trend else [],
        "recorded_today": any(m.role == "caregiver" and m.ts[:10] == today for m in msgs)
        or any(e.kind == "observation" and e.ts.date().isoformat() == today for e in timeline),
        "notes_count": len(
            next((d.items for d in reversed(docs) if d.doc_type == "caregiver_notes"), [])
        ),
    }


class GrantIn(BaseModel):
    member_id: str
    name: str = ""
    role: str
    scopes: list[str]
    valid_days: int | None = Field(default=None, ge=1, le=3650)
    granted_by: str | None = None
    purpose: str = ""
    allowed_purposes: list[str] = Field(default_factory=list)
    can_manage: bool = False


@app.get("/patients/{patient_id}/care-circle")
def care_circle_list(patient_id: str, x_who: str | None = Header(default=None)) -> dict[str, Any]:
    if not get_store().exists(patient_id):
        raise HTTPException(404, "unknown patient")
    _authorize(patient_id, x_who, "nurse")
    if not policy.is_manager(patient_id, x_who):
        raise HTTPException(403, "只有本人或此病人的受託管理者可查看授權名單")
    return {
        "health_id": get_store().load_profile(patient_id).health_id,
        "members": [m.model_dump(mode="json") for m in cc.members(patient_id)],
        "identities": cc.identities(),
    }


@app.post("/patients/{patient_id}/care-circle")
def care_circle_grant(
    patient_id: str, body: GrantIn, x_who: str | None = Header(default=None)
) -> dict[str, Any]:
    """Grant access (patient or family as proxy). Scopes are a subset of who|timeline|docs|talk."""
    from datetime import timedelta

    from record_schema import CareCircleMember

    store = get_store()
    if not store.exists(patient_id):
        raise HTTPException(404, "unknown patient")
    if not policy.is_manager(patient_id, x_who):
        raise HTTPException(403, "只有本人或此病人的受託管理者能授權")
    bad = [s for s in body.scopes if s not in cc.ALL_SCOPES]
    if bad or not body.scopes or body.role not in cc.DEFAULT_SCOPES:
        raise HTTPException(400, f"invalid scopes/role: {bad or body.role}")
    if not body.purpose.strip():
        raise HTTPException(400, "授權必須說明目的（purpose）")
    if not body.allowed_purposes or not set(body.allowed_purposes).issubset(cc.PURPOSES):
        raise HTTPException(400, "必須明確選擇有效的 allowed_purposes")
    member_identity = cc.whoami(body.member_id)
    if not member_identity or member_identity["role"] != body.role:
        raise HTTPException(400, "role 必須符合伺服器註冊身分")
    now = datetime.now(UTC)
    valid_to = now + timedelta(days=body.valid_days) if body.valid_days else None
    if x_who != patient_id:
        managers = [
            m for m in cc.active_members(patient_id) if m.member_id == x_who and m.can_manage
        ]
        # A delegate may choose the recipient's purpose, but cannot expand resources, its
        # own duration, re-delegate management, or change the owner's/self grant.
        if (
            body.can_manage
            or body.member_id in {patient_id, x_who}
            or not any(
                set(body.scopes).issubset(m.scopes)
                and (m.valid_to is None or (valid_to and valid_to <= m.valid_to))
                for m in managers
            )
        ):
            raise HTTPException(403, "代理授權不得提升或再委任自己的權限")
    m = cc.grant(
        patient_id,
        CareCircleMember(
            health_id=store.load_profile(patient_id).health_id,
            member_id=body.member_id,
            name=body.name or (cc.whoami(body.member_id) or {}).get("name", body.member_id),
            role=body.role,  # type: ignore[arg-type]
            scopes=body.scopes,  # type: ignore[arg-type]
            valid_from=now,
            valid_to=valid_to,
            granted_by=x_who or body.granted_by,
            purpose=body.purpose.strip(),
            allowed_purposes=body.allowed_purposes,
            can_manage=body.can_manage,
        ),
    )
    cc.log_access(patient_id, x_who, cc.role_of(patient_id, x_who), f"grant:{body.member_id}")
    return m.model_dump(mode="json")


@app.post("/patients/{patient_id}/care-circle/{member_id}/revoke")
def care_circle_revoke(
    patient_id: str, member_id: str, x_who: str | None = Header(default=None)
) -> dict[str, Any]:
    if not policy.is_manager(patient_id, x_who):
        raise HTTPException(403, "只有本人或此病人的受託管理者能撤銷")
    if x_who != patient_id and member_id == patient_id:
        raise HTTPException(403, "代理人不得撤銷本人權限")
    return {"revoked": cc.revoke(patient_id, member_id, x_who or "patient")}


@app.get("/patients/{patient_id}/access-log")
def patient_access_log(
    patient_id: str, limit: int = 50, x_who: str | None = Header(default=None)
) -> dict[str, Any]:
    """Patient/explicit delegate only; includes allowed and denied HTTP policy decisions."""
    if not get_store().exists(patient_id):
        raise HTTPException(404, "unknown patient")
    _role, tabs = _authorize(patient_id, x_who, "nurse")
    if "who" not in tabs or not policy.is_manager(patient_id, x_who):
        raise HTTPException(403, "未獲授權")
    legacy = [e.model_dump(mode="json") for e in cc.access_log(patient_id, limit)]
    fresh = security.audit_entries(patient_id, limit=max(1, min(limit, 500)))
    hid = get_store().load_profile(patient_id).health_id
    for row in fresh:
        row["health_id"] = hid
        row["what"] = row.get("action")
        row["who"] = row.get("who") or "anonymous"
        row["reason"] = row["details"].get("reason")
        row["request_id"] = row["details"].get("request_id")
    return {
        "items": sorted(legacy + fresh, key=lambda row: str(row.get("ts", "")), reverse=True)[
            : max(1, min(limit, 500))
        ]
    }


@app.get("/patients/{patient_id}/conversation")
def patient_conversation(patient_id: str, limit: int = 200) -> dict[str, Any]:
    return {
        "messages": [m.model_dump(mode="json") for m in conv.messages(patient_id, limit)],
        "session": (conv.session(patient_id).model_dump() if conv.session(patient_id) else None),
    }


class TalkIn(BaseModel):
    text: str
    role_view: str = "caregiver"


def _sse(event: str, data: Any) -> str:
    import json as _json

    data = policy.public_activity(data) if event == "event" else policy.project(data)
    return f"event: {event}\ndata: {_json.dumps(data, ensure_ascii=False, default=str)}\n\n"


def _talk_stream(
    patient_id: str,
    text: str,
    role_view: str,
    event_id: str | None = None,
    event_choice: str | None = None,
) -> StreamingResponse:
    """SSE for one caregiver turn (talk or four-button verification): activity events, streamed
    reply, done. Errors are surfaced, never a rule fallback."""
    from graphs.talk import run_turn

    def gen():
        import time as _time

        final: dict[str, Any] | None = None
        try:
            for kind, data in run_turn(
                patient_id,
                text,
                role_view,
                event_id,
                event_choice,
                actor_id=(policy.actor.get() or {}).get("who"),
            ):
                if kind == "event":
                    yield _sse("event", data)
                elif kind == "error":
                    yield _sse("error", data)
                    return
                else:
                    final = data
        except Exception as e:  # noqa: BLE001 - surface to the UI, never fall back
            log.exception("talk turn failed")
            yield _sse("error", {"detail": f"{type(e).__name__}: {e}"})
            return
        if final is None:
            yield _sse("error", {"detail": "no result"})
            return
        for line in final.get("system_lines") or []:
            yield _sse("system", {"text": line})
        reply = final.get("reply") or ""
        for i in range(0, len(reply), 3):  # 逐字串流
            yield _sse("token", {"text": reply[i : i + 3]})
            _time.sleep(0.02)
        events = final.get("events") or []
        yield _sse(
            "done",
            {
                "reply": reply,
                "kind": final.get("reply_kind"),
                "meta": final.get("reply_meta"),
                "phase": final.get("phase"),
                "red": final.get("red"),
                "thread_id": final.get("thread_id"),
                "sent": final.get("sent"),
                "steps": len(events),
                "ms": sum(e.get("ms", 0) for e in events if e.get("type") == "node_end"),
                "session": (
                    conv.session(patient_id).model_dump() if conv.session(patient_id) else None
                ),
            },
        )

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.post("/patients/{patient_id}/talk")
def patient_talk(
    patient_id: str, body: TalkIn, x_who: str | None = Header(default=None)
) -> StreamingResponse:
    """One caregiver message → SSE: activity events (node/llm/tool/red), streamed reply, done."""
    if not get_store().exists(patient_id):
        raise HTTPException(404, "unknown patient")
    if x_who and "talk" not in cc.scopes_for(patient_id, x_who):
        raise HTTPException(403, "未獲授權：沒有對話權限")
    cc.log_access(patient_id, x_who, cc.role_of(patient_id, x_who), "talk")
    if not body.text.strip():
        raise HTTPException(400, "empty message")
    role = (policy.actor.get() or {}).get("role", body.role_view)
    return _talk_stream(patient_id, body.text, "caregiver" if role == "family" else role)


# 照護者四鍵（唯一允許出現按鈕的地方）：選項 → 一句照護者原話，立即進現有追問流程
VERIFY_TEXT: dict[str, str] = {
    "with_patient": "我在他身邊，他剛剛可能跌倒了",
    "fine": "他沒事，跟平常一樣，站得起來，人清醒",
    "maybe_injured": "他可能跌倒受傷了",
    "unreachable": "聯絡不上他",
}


def verify_event(
    patient_id: str, event_id: str, choice: str, text: str = "", who: str | None = None
) -> tuple[str, str]:
    """Record the four-button answer on the sensor event; return (caregiver sentence, by)."""
    from record_schema import VERIFY_LABELS

    if choice not in VERIFY_TEXT:
        raise HTTPException(400, f"choice must be one of {list(VERIFY_TEXT)}")
    ev = sensor_events.get(patient_id, event_id)
    if ev is None:
        raise HTTPException(404, "unknown event")
    by = who or get_store().load_profile(patient_id).caregiver_code_name
    sensor_events.verify(patient_id, event_id, choice, text.strip(), by)
    s = conv.session(patient_id)
    if s and s.pending_event_id == event_id:
        s.pending_event_id = None
        conv.save_session(patient_id, s)
    sentence = VERIFY_TEXT[choice] + (f"。{text.strip()}" if text.strip() else "")
    cc.log_access(patient_id, who, cc.role_of(patient_id, who), f"verify:{VERIFY_LABELS[choice]}")
    return sentence, by


@app.post("/patients/{patient_id}/events/{event_id}/verify")
def patient_verify_event(
    patient_id: str, event_id: str, body: VerifyIn, x_who: str | None = Header(default=None)
) -> StreamingResponse:
    """Four-button verification of a「可能跌倒」event (我在他身邊／他沒事／他可能受傷／聯絡不上).
    The answer becomes a caregiver turn and enters the existing follow-up flow;「聯絡不上」trips
    RF12 and notifies the nurse at once. The reply lands in the IncidentFile's caregiver block."""
    if not get_store().exists(patient_id):
        raise HTTPException(404, "unknown patient")
    if x_who and "talk" not in cc.scopes_for(patient_id, x_who):
        raise HTTPException(403, "未獲授權：沒有對話權限")
    sentence, _by = verify_event(patient_id, event_id, body.choice, body.text, x_who)
    return _talk_stream(patient_id, sentence, "caregiver", event_id, body.choice)


@app.post("/round/start/stream")
def round_start_stream(body: RoundStartIn) -> StreamingResponse:
    """Round prep with live agent activity (node / subagent events), then the interrupt snapshot."""

    cohort = get_store().list_patients()

    def gen():
        for kind, data in runner.start_stream(
            "round", "ALL", {"round_date": body.round_date or datetime.now(UTC).date().isoformat()}
        ):
            if isinstance(data, dict) and data.get("thread_id"):
                policy.save_cohort(data["thread_id"], cohort)
            yield _sse(kind, data)

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# --- trends (nurse dashboard sparklines) -----------------------------------------------------


@app.get("/trends/{patient_id}")
def trends(patient_id: str, since: str | None = None, window_days: int = 7) -> dict[str, Any]:
    from datetime import date, timedelta

    from agents.subagents import trend_analyzer

    store = get_store()
    if not store.exists(patient_id):
        raise HTTPException(404, "unknown patient")
    until = datetime.now(UTC).date()
    s = date.fromisoformat(since) if since else until - timedelta(days=14)
    obs = store.load_timeline(patient_id, since=s, kinds={"observation"})
    inc = [e.id for e in store.load_timeline(patient_id, since=s, kinds={"incident"})]
    return trend_analyzer.analyze(patient_id, obs, inc, s, until, window_days).model_dump(
        mode="json"
    )  # type: ignore[arg-type]


# --- intake preview (照護者「是這個意思嗎」) --------------------------------------------------


class PreviewIn(BaseModel):
    patient_id: str
    text: str
    language: str = "zh-TW"
    followup_answers: list[FollowupQA] = Field(default_factory=list)


@app.post("/intake/preview")
def intake_preview(body: PreviewIn) -> dict[str, Any]:
    store = get_store()
    if not store.exists(body.patient_id):
        raise HTTPException(404, "unknown patient")
    obs = ingest_speech(
        body.text,
        body.language,
        store.load_profile(body.patient_id),
        store.load_baseline(body.patient_id),  # type: ignore[arg-type]
        followup_answers=body.followup_answers,
    )
    from red_flags.rules import RedFlagInput, evaluate

    profile = store.load_profile(body.patient_id)
    from baseline.loader import bands_for

    rf = evaluate(
        RedFlagInput(
            observation=obs,
            baseline_vitals=store.load_baseline(body.patient_id).vitals_usual,
            vitals_bands=bands_for(body.patient_id),  # type: ignore[arg-type]
            on_anticoagulant=profile.on_anticoagulant,
        )
    )
    return {
        "observation": obs.model_dump(mode="json"),
        "red_flags": rf.model_dump(mode="json"),
        "red_flag_lines": render_lines(rf),
    }


class TurnIn(BaseModel):
    patient_id: str
    turns: list[dict[str, Any]]
    seems_different: bool = False
    incidents: list[str] = Field(default_factory=list)
    dialog_id: str | None = None


@app.post("/intake/turn")
def intake_turn(body: TurnIn) -> dict[str, Any]:
    """One dialog step: merged observation, red flags, and the next question (or done)."""
    from ingest.intake_dialog import Turn, run_dialog

    store = get_store()
    if not store.exists(body.patient_id):
        raise HTTPException(404, "unknown patient")
    if not body.turns:
        raise HTTPException(400, "turns must contain the caregiver's first sentence")
    with tagged(dialog_id=body.dialog_id):
        res = run_dialog(
            [Turn.model_validate(x) for x in body.turns],
            store.load_profile(body.patient_id),
            store.load_baseline(body.patient_id),
            seems_different=body.seems_different,
            incidents=body.incidents,
        )
    return res.model_dump(mode="json")


# --- graph threads ----------------------------------------------------------------------------


class StartIn(BaseModel):
    patient_id: str
    dialog_id: str | None = None
    text: str = ""
    language: str = "zh-TW"
    turns: list[dict[str, Any]] = Field(default_factory=list)
    incidents: list[str] = Field(default_factory=list)
    caregiver_id: str | None = None
    shift: str | None = None
    seems_different: bool = False
    followup_answers: list[dict[str, Any]] = Field(default_factory=list)
    media_refs: list[str] = Field(default_factory=list)
    caregiver_confirmed_meaning: bool | None = None


def _raw(body: StartIn) -> dict[str, Any]:
    text = body.text or "。".join(str(x.get("text", "")) for x in body.turns if x.get("text"))
    return {
        "text": text,
        "dialog_id": body.dialog_id,
        "turns": body.turns,
        "incidents": body.incidents,
        "language": body.language,
        "caregiver_id": (policy.actor.get() or {}).get("who", body.caregiver_id),
        "shift": body.shift,
        "seems_different": body.seems_different,
        "followup_answers": body.followup_answers,
        "media_refs": body.media_refs,
        "caregiver_confirmed_meaning": body.caregiver_confirmed_meaning,
    }


@app.post("/path-a/start")
def path_a_start(body: StartIn) -> dict[str, Any]:
    if not get_store().exists(body.patient_id):
        raise HTTPException(404, "unknown patient")
    return _snapshot_view(
        runner.start("path_a", body.patient_id, {"path": "incident", "raw_input": _raw(body)})
    )


def _snapshot_view(snap: dict[str, Any]) -> dict[str, Any]:
    if (policy.actor.get() or {}).get("role", "nurse") == "nurse":
        return snap
    return {
        "thread_id": snap["thread_id"],
        "graph": snap["graph"],
        "status": snap["status"],
        "interrupt": {"type": (snap.get("interrupt") or {}).get("type")},
        "handoff": {"thread_id": snap["handoff"]["thread_id"]} if snap.get("handoff") else None,
    }


@app.post("/shift/start")
def shift_start(body: StartIn) -> dict[str, Any]:
    if not get_store().exists(body.patient_id):
        raise HTTPException(404, "unknown patient")
    snap = runner.start("shift", body.patient_id, {"path": "routine", "raw_input": _raw(body)})
    if snap["values"].get("handoff_to_path_a"):
        # 紅燈：轉入 Path A（同一句話，不經草稿）
        a = runner.start("path_a", body.patient_id, {"path": "incident", "raw_input": _raw(body)})
        snap["handoff"] = {"thread_id": a["thread_id"], "interrupt": a["interrupt"]}
    return _snapshot_view(snap)


@app.post("/round/start")
def round_start(body: RoundStartIn) -> dict[str, Any]:
    cohort = get_store().list_patients()
    snap = runner.start(
        "round", "ALL", {"round_date": body.round_date or datetime.now(UTC).date().isoformat()}
    )
    policy.save_cohort(snap["thread_id"], cohort)
    return snap


@app.get("/threads")
def threads(status: str | None = None, graph: str | None = None) -> list[dict[str, Any]]:
    rows = registry.list_threads(status=status, graph=graph)
    return [
        {
            **r,
            "deadline": r["deadline"].isoformat() if r.get("deadline") else None,
            "created_at": r["created_at"].isoformat() if r.get("created_at") else None,
            "updated_at": r["updated_at"].isoformat() if r.get("updated_at") else None,
        }
        for r in rows
        if policy.thread_visible(r["thread_id"])
    ]


@app.get("/threads/{thread_id:path}/state")
def thread_state(thread_id: str) -> dict[str, Any]:
    try:
        return runner.snapshot(thread_id)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(404, f"unknown thread: {e}") from e


def _system_events_after(snap: dict[str, Any], payload: dict[str, Any]) -> None:
    """Nurse / round actions show up in the resident's conversation as centered system lines."""
    vals = snap.get("values", {})
    who = payload.get("nurse_id") or payload.get("head_nurse") or "護理師"
    try:
        if snap["graph"] == "shift" and snap["status"] == "done":
            conv.system_event(
                vals["patient_id"],
                f"護理師 {who} 已確認今天的紀錄。",
                {"thread_id": snap["thread_id"]},
            )
        elif snap["graph"] == "path_a" and snap["status"] == "done":
            conv.system_event(
                vals["patient_id"],
                f"護理師 {who} 已完成事故紀錄與家屬通知。",
                {"thread_id": snap["thread_id"]},
            )
        elif snap["graph"] == "round" and snap["status"] == "done":
            for o in vals.get("orders", []):
                conv.system_event(
                    o["patient_id"],
                    f"醫囑已更新：{o['raw_text'][:60]}",
                    {"thread_id": snap["thread_id"]},
                )
    except Exception as e:  # noqa: BLE001
        log.warning("system event failed: %s", e)


@app.post("/threads/{thread_id:path}/resume")
def thread_resume(thread_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    if policy.actor.get():
        payload = {
            **payload,
            "nurse_id": policy.current()["who"],
            "head_nurse": policy.current()["who"],
        }
    try:
        snap = runner.resume(thread_id, payload)
        _system_events_after(snap, payload)
        return snap
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    except AssertionError as e:
        raise HTTPException(422, str(e)) from e


class CaregiverReportIn(BaseModel):
    turns: list[dict[str, Any]]
    incidents: list[str] = Field(default_factory=list)
    seems_different: bool = False


@app.post("/threads/{thread_id:path}/caregiver-report")
def caregiver_report(thread_id: str, body: CaregiverReportIn) -> dict[str, Any]:
    """紅燈後對話不結束：照護者的每個回答即時寫進 caregiver_section，護理師端同步更新。"""
    try:
        return _snapshot_view(
            runner.update_caregiver(thread_id, body.turns, body.incidents, body.seems_different)
        )
    except ValueError as e:
        raise HTTPException(409, str(e)) from e


@app.get("/debug/trace/{thread_id:path}")
def debug_trace(thread_id: str) -> dict[str, Any]:
    """One conversation's agent calls: per-turn prompt summary, output, reason, duration."""
    try:
        snap = runner.snapshot(thread_id)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(404, f"unknown thread: {e}") from e
    vals = snap["values"]
    dialog_id = (vals.get("raw_input") or {}).get("dialog_id")
    run_ids = {m.get("run_id") for m in vals.get("agent_runs", []) if m.get("run_id")}
    hr = ((vals.get("documents") or {}).get("handoff_agent_run") or {}).get("run_id")
    if hr:
        run_ids.add(hr)
    entries = for_ids(thread_id=thread_id, dialog_id=dialog_id, run_ids=run_ids or None)
    turns = [
        {
            "ts": e["ts"],
            "prompt_summary": (e.get("input") or "")[:400],
            "output": e.get("output"),
            "reason": e.get("reason"),
            "duration_ms": e.get("duration_ms"),
            "error": e.get("error"),
            "provider": e.get("provider"),
        }
        for e in entries
        if e["kind"] == "llm.next_question"
    ]
    llm_calls = [
        {
            "ts": e["ts"],
            "kind": e["kind"],
            "provider": e.get("provider"),
            "duration_ms": e.get("duration_ms"),
            "prompt_summary": (e.get("input") or e.get("prompt") or "")[:300],
            "output": e.get("output"),
            "reason": e.get("reason"),
            "error": e.get("error"),
        }
        for e in entries
        if e["kind"].startswith("llm.")
    ]
    agent_runs = [e for e in entries if e["kind"] == "deep_agent.run"]
    tool_calls = [e for e in entries if e["kind"] == "subagent.tool"]
    return {
        "thread_id": thread_id,
        "dialog_id": dialog_id,
        "graph": snap["graph"],
        "status": snap["status"],
        "turns": turns,
        "llm_calls": llm_calls,
        "agent_runs": agent_runs,
        "subagent_tool_calls": tool_calls,
        "counts": {
            "llm_calls": len(llm_calls),
            "agent_runs": len(agent_runs),
            "subagent_tool_calls": len(tool_calls),
        },
    }


@app.get("/trace")
def get_trace(
    kind: str | None = None, limit: int = 100, contains: str | None = None
) -> list[dict[str, Any]]:
    """Agent / LLM call trace (also written to records/_trace/*.jsonl)."""
    from core.trace import recent

    rows = recent(kind=kind, limit=min(limit, 500), contains=contains)
    if policy.actor.get() is None:
        return rows
    return [
        r
        for r in rows
        if (r.get("patient_id") or r.get("thread_id"))
        and (not r.get("patient_id") or policy.visible(r["patient_id"]))
        and (not r.get("thread_id") or policy.thread_visible(r["thread_id"]))
    ]


def _code_name(pid: str | None) -> str | None:
    store = get_store()
    if not pid or not store.exists(pid):
        return None
    return store.load_profile(pid).code_name


@app.get("/nurse/inbox")
def nurse_inbox() -> dict[str, Any]:
    """一屏看完：紅燈置頂，然後待審核（Path A）、待 10 秒確認（Path B）、巡診待辦。"""
    items: list[dict[str, Any]] = []
    for row in registry.list_threads(status="interrupted"):
        if not policy.thread_visible(row["thread_id"]):
            continue
        snap = runner.snapshot(row["thread_id"])
        itype = (snap["interrupt"] or {}).get("type")
        vals = snap["values"]
        red = bool((vals.get("red_flags") or {}).get("notify_now"))
        items.append(
            {
                "thread_id": row["thread_id"],
                "graph": row["graph"],
                "patient_id": vals.get("patient_id", "ALL"),
                "code_name": _code_name(vals.get("patient_id")),
                "caregiver_reports": (vals.get("caregiver_reports") or [])[-5:],
                "turn_count": len(vals.get("caregiver_reports") or []),
                "interrupt_type": itype,
                "red_flag": red,
                "red_flag_lines": render_lines(
                    __import__("record_schema").RedFlagResult.model_validate(vals["red_flags"])
                )
                if vals.get("red_flags")
                else [],
                "deadline": vals.get("deadline"),
                "escalation_level": vals.get("escalation_level", 0),
                "updated_at": vals.get("updated_at"),
                "summary": (vals.get("minimal_sbar") or {}).get("s")
                or (vals.get("sbar") or {}).get("situation")
                or "",
            }
        )
    order = {"nurse_onsite_assessment": 0, "nurse_review": 1, "nurse_10s_confirm": 2}
    items.sort(
        key=lambda i: (not i["red_flag"], order.get(i["interrupt_type"], 9), i["updated_at"] or "")
    )
    events = []
    for pid in policy.visible_patients():
        for e in sensor_events.list_events(pid):
            if e.status == "closed":
                continue
            events.append({**sensor_events.nurse_view(e), "code_name": _code_name(pid)})
    events.sort(key=lambda e: e["ts"], reverse=True)
    return {
        "items": items,
        "events": events,  # 新事件（含感測原始值，只給護理師）
        "worker_scan_interval_s": get_settings().WORKER_SCAN_INTERVAL_S,
    }


@app.post("/worker/scan")
def worker_scan() -> dict[str, Any]:
    """Manual trigger of the timeout scan (the scheduler runs it every WORKER_SCAN_INTERVAL_S)."""
    return {"escalated": worker.scan_once()}


# --- other channels (mock / hardcoded) --------------------------------------------------------


@app.get("/ingest/vitals/{patient_id}")
def vitals(patient_id: str, shift: str = "day") -> dict[str, Any]:
    return vitals_ingest.measure(patient_id, datetime.now(UTC).date(), shift).model_dump(
        mode="json"
    )


class OrderPreviewIn(BaseModel):
    text: str


@app.post("/ingest/order/preview")
def order_preview(body: OrderPreviewIn) -> dict[str, Any]:
    items = doctor_order.parse_order(body.text)
    return {
        "items": [i.model_dump(mode="json") for i in items],
        "caregiver_notes_zh": doctor_order.caregiver_notes_zh(items),
    }


@app.get("/ingest/discharge/{patient_id}")
def discharge(patient_id: str) -> dict[str, Any]:
    summary = discharge_pdf.ingest(patient_id)
    return {
        "summary": summary.model_dump(mode="json"),
        "baseline_proposal": discharge_pdf.to_baseline_proposal(patient_id, summary).model_dump(
            mode="json"
        ),
        "mock": True,
    }


@app.post("/ingest/fhir/{patient_id}")
def fhir_import(patient_id: str, body: dict[str, Any]) -> dict[str, Any]:
    """Import a synthetic FHIR Bundle; normalized data remains pending nurse review."""
    return fhir_bundle.import_bundle(patient_id, body).model_dump(mode="json")


@app.get("/ingest/fhir/{patient_id}")
def fhir_export(patient_id: str, import_id: str | None = None) -> dict[str, Any]:
    return fhir_bundle.export_bundle(patient_id, import_id)
