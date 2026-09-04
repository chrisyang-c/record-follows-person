"""FastAPI — the record speaks through here. All graph interaction is start / resume / snapshot."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from record_schema import DIMENSION_LABELS, DIMENSIONS, FollowupQA

from core.settings import get_settings
from graphs import registry, runner, worker
from graphs.checkpointer import is_postgres
from ingest import discharge_pdf, doctor_order
from ingest import vitals as vitals_ingest
from ingest.caregiver_speech import ingest as ingest_speech
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
        "llm_mode": s.LLM_MODE,
        "llm_enabled": s.llm_enabled,
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
    out = []
    for pid in store.list_patients():
        p = store.load_profile(pid)
        tl = store.load_timeline(pid)
        out.append(
            {
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
        )
    return out


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


# --- graph threads ----------------------------------------------------------------------------


class StartIn(BaseModel):
    patient_id: str
    text: str
    language: str = "zh-TW"
    caregiver_id: str | None = None
    shift: str | None = None
    seems_different: bool = False
    followup_answers: list[dict[str, Any]] = Field(default_factory=list)
    media_refs: list[str] = Field(default_factory=list)
    caregiver_confirmed_meaning: bool | None = None


def _raw(body: StartIn) -> dict[str, Any]:
    return {
        "text": body.text,
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


class RoundStartIn(BaseModel):
    round_date: str | None = None


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


@app.post("/threads/{thread_id:path}/resume")
def thread_resume(thread_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    try:
        return runner.resume(thread_id, payload)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    except AssertionError as e:
        raise HTTPException(422, str(e)) from e


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
    return {"items": items, "worker_scan_interval_s": get_settings().WORKER_SCAN_INTERVAL_S}


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
