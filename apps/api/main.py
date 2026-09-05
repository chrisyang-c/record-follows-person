"""FastAPI — the record speaks through here. All graph interaction is start / resume / snapshot."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import Any

from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from record_schema import DIMENSION_LABELS, DIMENSIONS, FollowupQA

from agents.personal import AgentDidNotDeliver
from core.llm import LLMUnavailable
from core.settings import get_settings
from core.trace import for_ids, tagged
from graphs import registry, runner, worker
from graphs.checkpointer import is_postgres
from ingest import discharge_pdf, doctor_order
from ingest import vitals as vitals_ingest
from ingest.caregiver_speech import ingest as ingest_speech
from record import care_circle as cc
from record import conversation as conv
from record import events as sensor_events
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


@app.exception_handler(LLMUnavailable)
async def _llm_unavailable(_req, exc: LLMUnavailable):
    """No model / model call failed → visible error, never a rule fallback."""
    from fastapi.responses import JSONResponse

    return JSONResponse(status_code=503, content={"detail": f"LLM 未設定或呼叫失敗：{exc}"})


@app.exception_handler(AgentDidNotDeliver)
async def _agent_failed(_req, exc: AgentDidNotDeliver):
    from fastapi.responses import JSONResponse

    return JSONResponse(status_code=503, content={"detail": f"agent 沒有產出：{exc}"})


app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
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
        "records": get_store().list_patients(),
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
    return [_resident_row(store, pid) for pid in store.list_patients()]


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
        return {
            "recorded_today": any(m.role == "caregiver" and m.ts[:10] == today for m in msgs)
            or any(
                e.ts.date().isoformat() == today
                for e in store.load_timeline(pid, kinds={"observation"})
            ),
            "notes_count": len(notes),
            "session_phase": s.phase if s and s.phase != "closed" else None,
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
    return {
        "abnormal": [line.model_dump(mode="json") for line in abnormal],
        "series": [s.model_dump(mode="json") for s in rep.series if s.dimension in dims],
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
            for pid in store.list_patients()
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
    changed = [
        d.dimension
        for d in (latest.deltas if latest else [])
        if getattr(d, "is_change", getattr(d, "changed", False))
    ]
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
    return [d.model_dump(mode="json") for d in store.load_documents(patient_id, doc_type)]


@app.get("/records/{patient_id}/documents/{doc_id}")
def document(patient_id: str, doc_id: str) -> dict[str, Any]:
    d = get_store().get_document(patient_id, doc_id)
    if d is None:
        raise HTTPException(404, "unknown document")
    return d.model_dump(mode="json")


@app.get("/records/{patient_id}/provenance")
def provenance(patient_id: str) -> list[dict[str, Any]]:
    return [line.model_dump(mode="json") for line in get_store().read_provenance(patient_id)]


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
    """Who is looking, and which tabs the Care Circle lets them see. No member → 403「未獲授權」.
    Without X-Who (older clients / tests) fall back to the X-Role header with that role's default
    scopes so nothing silently widens: the role must still exist in DEFAULT_SCOPES."""
    if who:
        scopes = cc.scopes_for(patient_id, who)
        if not scopes:
            raise HTTPException(403, "未獲授權：你不在這個人的 Care Circle 裡")
        role = cc.role_of(patient_id, who) or "caregiver"
        return role, list(scopes)
    role = (x_role or "nurse").lower()
    if role not in cc.DEFAULT_SCOPES:
        raise HTTPException(403, "未獲授權")
    return role, list(cc.DEFAULT_SCOPES[role])  # type: ignore[index]


@app.get("/whoami")
def whoami(me: str | None = None) -> dict[str, Any]:
    """The web stores only「我是誰」(cookie ``me``); role and display name come from here."""
    it = cc.whoami(me)
    if not it:
        raise HTTPException(404, "unknown identity")
    return it


@app.get("/patients/{patient_id}/summary")
def patient_summary(
    patient_id: str,
    tab: str | None = None,
    x_role: str | None = Header(default=None),
    x_who: str | None = Header(default=None),
) -> dict[str, Any]:
    """who / timeline / docs / talk in one call. Caregivers only see what they recorded.
    Access is a Care Circle lookup (X-Who); every read is logged (「誰看過我的紀錄」)."""
    from datetime import date, timedelta

    from agents.subagents import trend_analyzer

    store = get_store()
    if not store.exists(patient_id):
        raise HTTPException(404, "unknown patient")
    role, allowed_tabs = _authorize(patient_id, x_who, x_role)
    cc.log_access(patient_id, x_who, role, f"summary:{tab}" if tab else "summary")  # type: ignore[arg-type]
    if role in ("patient", "family"):
        role = "caregiver" if role == "family" else "patient"
    profile = store.load_profile(patient_id)
    baseline = store.load_baseline(patient_id)
    timeline = store.load_timeline(patient_id)
    if role == "caregiver":
        cg = profile.caregiver_code_name
        timeline = [
            e
            for e in timeline
            if e.kind == "observation"
            and (
                e.observation.domains
                and any(
                    dv.provenance.author in (cg, "intake_agent")
                    for dv in e.observation.domains.values()
                )
                or True
            )
        ]
        timeline = [e for e in timeline if e.kind == "observation"]
    docs = store.load_documents(patient_id)
    if role == "caregiver":
        docs = [d for d in docs if d.doc_type == "caregiver_notes"]
    until = datetime.now(UTC).date()
    since = until - timedelta(days=14)
    obs = store.load_timeline(patient_id, since=since, kinds={"observation"})
    trend = trend_analyzer.analyze(patient_id, obs, [], since, until, baseline=baseline)  # type: ignore[arg-type]
    msgs = conv.messages(patient_id)
    today = date.today().isoformat()
    return {
        "role": role,
        "who": x_who,
        "allowed_tabs": allowed_tabs,
        "profile": profile.model_dump(mode="json"),
        "baseline": baseline.model_dump(mode="json"),
        "timeline": [e.model_dump(mode="json") for e in timeline],
        "documents": [d.model_dump(mode="json") for d in docs],
        "conversation": [m.model_dump(mode="json") for m in msgs],
        "session": (conv.session(patient_id).model_dump() if conv.session(patient_id) else None),
        "pending": _pending_for(patient_id) if role != "caregiver" else [],
        "sensor_events": [
            (sensor_events.nurse_view if role == "nurse" else sensor_events.public_view)(e)
            for e in sensor_events.list_events(patient_id)[-5:]
        ],
        "changed_dimensions": [line.dimension for line in trend.lines if line.is_abnormal],
        "trend_lines": [line.model_dump(mode="json") for line in trend.lines],
        "recorded_today": any(m.role == "caregiver" and m.ts[:10] == today for m in msgs)
        or any(e.kind == "observation" and e.ts.date().isoformat() == today for e in timeline),
        "notes_count": len(
            next(
                (d.items for d in reversed(store.load_documents(patient_id, "caregiver_notes"))), []
            )
        ),
    }


class GrantIn(BaseModel):
    member_id: str
    name: str = ""
    role: str
    scopes: list[str]
    valid_days: int | None = None
    granted_by: str


@app.get("/patients/{patient_id}/care-circle")
def care_circle_list(patient_id: str, x_who: str | None = Header(default=None)) -> dict[str, Any]:
    if not get_store().exists(patient_id):
        raise HTTPException(404, "unknown patient")
    _authorize(patient_id, x_who, "nurse")
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
    if cc.role_of(patient_id, x_who) not in ("patient", "family"):
        raise HTTPException(403, "只有本人或家屬能授權")
    bad = [s for s in body.scopes if s not in cc.ALL_SCOPES]
    if bad or body.role not in cc.DEFAULT_SCOPES:
        raise HTTPException(400, f"invalid scopes/role: {bad or body.role}")
    now = datetime.now(UTC)
    m = cc.grant(
        patient_id,
        CareCircleMember(
            health_id=store.load_profile(patient_id).health_id,
            member_id=body.member_id,
            name=body.name or (cc.whoami(body.member_id) or {}).get("name", body.member_id),
            role=body.role,  # type: ignore[arg-type]
            scopes=body.scopes,  # type: ignore[arg-type]
            valid_from=now,
            valid_to=now + timedelta(days=body.valid_days) if body.valid_days else None,
            granted_by=x_who or body.granted_by,
        ),
    )
    cc.log_access(patient_id, x_who, cc.role_of(patient_id, x_who), f"grant:{body.member_id}")
    return m.model_dump(mode="json")


@app.post("/patients/{patient_id}/care-circle/{member_id}/revoke")
def care_circle_revoke(
    patient_id: str, member_id: str, x_who: str | None = Header(default=None)
) -> dict[str, Any]:
    if cc.role_of(patient_id, x_who) not in ("patient", "family"):
        raise HTTPException(403, "只有本人或家屬能撤銷")
    return {"revoked": cc.revoke(patient_id, member_id, x_who or "patient")}


@app.get("/patients/{patient_id}/access-log")
def patient_access_log(
    patient_id: str, limit: int = 50, x_who: str | None = Header(default=None)
) -> dict[str, Any]:
    """「誰看過我的紀錄」：誰、看了什麼、何時。Anyone with `who` scope may read it."""
    if not get_store().exists(patient_id):
        raise HTTPException(404, "unknown patient")
    _role, tabs = _authorize(patient_id, x_who, "nurse")
    if "who" not in tabs:
        raise HTTPException(403, "未獲授權")
    return {"items": [e.model_dump(mode="json") for e in cc.access_log(patient_id, limit)]}


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

    return f"event: {event}\ndata: {_json.dumps(data, ensure_ascii=False, default=str)}\n\n"


@app.post("/patients/{patient_id}/talk")
def patient_talk(
    patient_id: str, body: TalkIn, x_who: str | None = Header(default=None)
) -> StreamingResponse:
    """One caregiver message → SSE: activity events (node/llm/tool/red), streamed reply, done."""
    from graphs.talk import run_turn

    if not get_store().exists(patient_id):
        raise HTTPException(404, "unknown patient")
    if x_who and "talk" not in cc.scopes_for(patient_id, x_who):
        raise HTTPException(403, "未獲授權：沒有對話權限")
    cc.log_access(patient_id, x_who, cc.role_of(patient_id, x_who), "talk")
    if not body.text.strip():
        raise HTTPException(400, "empty message")

    def gen():
        import time as _time

        final: dict[str, Any] | None = None
        try:
            for kind, data in run_turn(patient_id, body.text, body.role_view):
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
        text = final.get("reply") or ""
        for i in range(0, len(text), 3):  # 逐字串流
            yield _sse("token", {"text": text[i : i + 3]})
            _time.sleep(0.02)
        events = final.get("events") or []
        yield _sse(
            "done",
            {
                "reply": text,
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


@app.post("/round/start/stream")
def round_start_stream(body: RoundStartIn) -> StreamingResponse:
    """Round prep with live agent activity (node / subagent events), then the interrupt snapshot."""

    def gen():
        for kind, data in runner.start_stream(
            "round", "ALL", {"round_date": body.round_date or datetime.now(UTC).date().isoformat()}
        ):
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
    rf = evaluate(
        RedFlagInput(
            observation=obs,
            baseline_vitals=store.load_baseline(body.patient_id).vitals_usual,
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
        "caregiver_id": body.caregiver_id,
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
    return runner.start("path_a", body.patient_id, {"path": "incident", "raw_input": _raw(body)})


@app.post("/shift/start")
def shift_start(body: StartIn) -> dict[str, Any]:
    if not get_store().exists(body.patient_id):
        raise HTTPException(404, "unknown patient")
    snap = runner.start("shift", body.patient_id, {"path": "routine", "raw_input": _raw(body)})
    if snap["values"].get("handoff_to_path_a"):
        # 紅燈：轉入 Path A（同一句話，不經草稿）
        a = runner.start("path_a", body.patient_id, {"path": "incident", "raw_input": _raw(body)})
        snap["handoff"] = {"thread_id": a["thread_id"], "interrupt": a["interrupt"]}
    return snap


@app.post("/round/start")
def round_start(body: RoundStartIn) -> dict[str, Any]:
    return runner.start(
        "round", "ALL", {"round_date": body.round_date or datetime.now(UTC).date().isoformat()}
    )


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
        return runner.update_caregiver(thread_id, body.turns, body.incidents, body.seems_different)
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

    return recent(kind=kind, limit=min(limit, 500), contains=contains)


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
    store = get_store()
    for pid in store.list_patients():
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
