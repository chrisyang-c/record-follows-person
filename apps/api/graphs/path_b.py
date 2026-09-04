"""Path B — 日常 → 本地歷史 → 巡診. Node names == docs/langgraph_path_b_routine_round.mermaid.

Two graphs: SHIFT (every shift, per person) and ROUND (before each doctor's round, whole floor).
◇ interrupts: nurse_10s_confirm | head_nurse_edit_list, doctor_round, nurse_confirm_baseline.
"""

from __future__ import annotations

import logging
import operator
from datetime import UTC, date, datetime, timedelta
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, Send, interrupt
from record_schema import (
    BaselineDelta,
    BaselineEntry,
    BaselineProposal,
    CaregiverNotes,
    Encounter,
    MinimalSBAR,
    Observation,
    Order,
    Provenance,
    RedFlagResult,
    RoundPage,
    StructuredObservation,
    TrendReport,
    Vitals,
)

from agents.subagents import trend_analyzer as ta
from core.ids import new_id
from core.llm import get_llm
from graphs.common import (
    baseline_comparator,
    deadline_iso,
    guarded_timeline_write,
    intake_agent,
    load_person_record,
    notify_nurse_urgent,
    now_iso,
    red_flag_hit,
    red_flag_rules,
)
from ingest import doctor_order
from ingest import vitals as vitals_ingest
from record.store import get_store

log = logging.getLogger(__name__)

# =============================================================================================
# SHIFT — 每班：照護者一句話
# =============================================================================================


class ShiftState(TypedDict, total=False):
    patient_id: str
    thread_id: str
    path: str
    raw_input: dict[str, Any]
    caregiver_addendum: str | None
    caregiver_addenda: Annotated[list[str], operator.add]
    asked_dimensions: list[str]
    turn_count: int
    profile: dict[str, Any]
    baseline: dict[str, Any]
    recent_lines: list[str]
    recent_observations: list[dict[str, Any]]
    structured_observation: dict[str, Any]
    baseline_delta: list[dict[str, Any]]
    red_flags: dict[str, Any]
    minimal_sbar: dict[str, Any]
    confirm_decision: dict[str, Any]
    written_id: str
    curated: dict[str, Any]
    handoff_to_path_a: bool
    notifications: Annotated[list[dict[str, Any]], operator.add]
    review_log: Annotated[list[dict[str, Any]], operator.add]
    status: str
    deadline: str | None
    updated_at: str


def to_path_a(state: ShiftState) -> dict[str, Any]:
    return {
        "handoff_to_path_a": True,
        "status": "to_path_a",
        "deadline": None,
        "updated_at": now_iso(),
    }


def minimal_sbar_draft(state: ShiftState) -> dict[str, Any]:
    obs = StructuredObservation.model_validate(state["structured_observation"])
    deltas = [BaselineDelta.model_validate(d) for d in state.get("baseline_delta", [])]
    sbar = get_llm().minimal_sbar(obs, deltas)
    assert sbar.status == "draft" and sbar.author == "ai"
    return {
        "minimal_sbar": sbar.model_dump(mode="json"),
        "deadline": deadline_iso(),
        "status": "awaiting_10s_confirm",
        "updated_at": now_iso(),
    }


def nurse_10s_confirm(state: ShiftState) -> dict[str, Any]:
    decision = interrupt(
        {
            "type": "nurse_10s_confirm",
            "patient_id": state["patient_id"],
            "minimal_sbar": state.get("minimal_sbar"),
            "structured_observation": state.get("structured_observation"),
            "baseline_delta": state.get("baseline_delta", []),
            "red_flags": state.get("red_flags"),
            "allowed_actions": ["accept", "edit", "return"],
        }
    )
    action = decision.get("action", "accept")
    entry = {
        "node": "nurse_10s_confirm",
        "action": action,
        "by": decision.get("nurse_id"),
        "ts": now_iso(),
    }
    update: dict[str, Any] = {
        "confirm_decision": decision,
        "review_log": [entry],
        "updated_at": now_iso(),
    }
    if action == "return":
        update["caregiver_addendum"] = decision.get("caregiver_addendum")
        if decision.get("caregiver_addendum"):
            update["caregiver_addenda"] = [decision["caregiver_addendum"]]
        update["status"] = "returned_to_intake"
    else:
        update["status"] = "confirmed"
        update["deadline"] = None
    return update


def route_after_confirm(state: ShiftState) -> str:
    return (
        "intake_agent"
        if (state.get("confirm_decision") or {}).get("action") == "return"
        else "timeline_write"
    )


def shift_timeline_write(state: ShiftState) -> dict[str, Any]:
    decision = state["confirm_decision"]
    nurse_id = decision.get("nurse_id", "nurse")
    ts = datetime.now(UTC)
    obs = StructuredObservation.model_validate(state["structured_observation"])
    sbar = MinimalSBAR.model_validate(state["minimal_sbar"])
    if decision.get("action") == "edit":
        sbar.nurse_edit = decision.get("edited_a") or decision.get("edited_s")
        if decision.get("edited_s"):
            sbar.s = decision["edited_s"]
        if decision.get("edited_a"):
            sbar.a_change_vs_baseline = decision["edited_a"]
        sbar.author = "nurse"
    sbar.status = "approved"
    sbar.confirmed_by = nurse_id
    raw = state.get("raw_input", {})
    shift = raw.get("shift") or ("night" if ts.hour >= 20 or ts.hour < 6 else "day")
    v_in = decision.get("vitals")
    vitals = (
        Vitals(**{**v_in, "measured_by": nurse_id, "ts": ts})
        if v_in
        else vitals_ingest.measure(state["patient_id"], ts.date(), shift)
    )
    entry = Observation(
        id=new_id("obs", ts),
        patient_id=state["patient_id"],
        ts=ts,
        status="approved",
        confirmed_by=nurse_id,
        provenance=Provenance(
            source="nurse_confirmed",
            author=nurse_id,
            confirmed_by=nurse_id,
            ts=ts,
            language_original=obs.language,
        ),
        shift=shift,  # type: ignore[arg-type]
        observation=obs,
        deltas=[BaselineDelta.model_validate(d) for d in state.get("baseline_delta", [])],
        minimal_sbar=sbar,
        vitals=vitals,
        red_flags=RedFlagResult.model_validate(state["red_flags"])
        if state.get("red_flags")
        else None,
    )
    assert entry.status == "approved" and entry.confirmed_by, "timeline_write requires approval"
    wid = guarded_timeline_write(state["patient_id"], entry)
    return {"written_id": wid, "status": "written", "updated_at": now_iso()}


def timeline_curator(state: ShiftState) -> dict[str, Any]:
    """Background structure-only pass: link today's observation to same-day incidents/orders.

    It never writes prose and never touches existing timeline entries (append-only)."""
    store = get_store()
    pid = state["patient_id"]
    today = datetime.now(UTC).date()
    same_day = [e for e in store.load_timeline(pid, since=today) if e.kind in ("incident", "order")]
    obs_today = [e for e in store.load_timeline(pid, since=today, kinds={"observation"})]
    dup_hint = [
        e.id
        for e in obs_today
        if e.id != state.get("written_id")
        and e.observation.raw_text == state["structured_observation"]["raw_text"]
    ]
    curated = {
        "written_id": state.get("written_id"),
        "related_ids": [e.id for e in same_day],
        "possible_duplicates": dup_hint,
        "normalized_units": {"temp": "°C", "bp": "mmHg", "spo2": "%"},
    }
    return {"curated": curated, "status": "done", "updated_at": now_iso()}


def build_shift_graph() -> StateGraph:
    g = StateGraph(ShiftState)
    g.add_node("load_person_record", load_person_record)
    g.add_node("intake_agent", intake_agent)
    g.add_node("baseline_comparator", baseline_comparator)
    g.add_node("red_flag_rules", red_flag_rules)
    g.add_node("notify_nurse_urgent", notify_nurse_urgent)
    g.add_node("to_path_a", to_path_a)
    g.add_node("minimal_sbar_draft", minimal_sbar_draft)
    g.add_node("nurse_10s_confirm", nurse_10s_confirm)
    g.add_node("timeline_write", shift_timeline_write)
    g.add_node("timeline_curator", timeline_curator)
    g.add_edge(START, "load_person_record")
    g.add_edge("load_person_record", "intake_agent")
    g.add_edge("intake_agent", "baseline_comparator")
    g.add_edge("baseline_comparator", "red_flag_rules")
    g.add_conditional_edges(
        "red_flag_rules",
        lambda s: "notify_nurse_urgent" if red_flag_hit(s) else "minimal_sbar_draft",
        ["notify_nurse_urgent", "minimal_sbar_draft"],
    )
    g.add_edge("notify_nurse_urgent", "to_path_a")
    g.add_edge("to_path_a", END)
    g.add_edge("minimal_sbar_draft", "nurse_10s_confirm")
    g.add_conditional_edges(
        "nurse_10s_confirm", route_after_confirm, ["intake_agent", "timeline_write"]
    )
    g.add_edge("timeline_write", "timeline_curator")
    g.add_edge("timeline_curator", END)
    return g


# =============================================================================================
# ROUND — 巡診前 1–2 天：全院一次
# =============================================================================================


class RoundState(TypedDict, total=False):
    thread_id: str
    patient_id: str  # "ALL"
    round_date: str
    since: str
    roster: list[dict[str, Any]]
    trends: Annotated[list[dict[str, Any]], operator.add]
    round_pages: Annotated[list[dict[str, Any]], operator.add]
    agent_runs: Annotated[list[dict[str, Any]], operator.add]
    head_nurse_decision: dict[str, Any]
    published: list[str]
    orders_input: list[dict[str, Any]]
    orders: list[dict[str, Any]]
    encounters: list[dict[str, Any]]
    caregiver_notes: list[dict[str, Any]]
    baseline_proposals: list[dict[str, Any]]
    baseline_decision: dict[str, Any]
    baseline_written: list[str]
    written_ids: list[str]
    review_log: Annotated[list[dict[str, Any]], operator.add]
    status: str
    deadline: str | None
    updated_at: str


class PersonTask(TypedDict, total=False):
    patient_id: str
    since: str
    until: str
    report: dict[str, Any]
    thread_id: str
    trend_meta: dict[str, Any]


def _last_round_date(pid: str, fallback: date) -> date:
    encs = [
        e
        for e in get_store().load_timeline(pid, kinds={"encounter"})
        if e.encounter_type == "round"
    ]
    return encs[-1].ts.date() if encs else fallback


def roster_agent(state: RoundState) -> dict[str, Any]:
    store = get_store()
    round_date = date.fromisoformat(state.get("round_date") or datetime.now(UTC).date().isoformat())
    rows: list[dict[str, Any]] = []
    since_all: date | None = None
    for pid in store.list_patients():
        since = _last_round_date(pid, round_date - timedelta(days=30))
        since_all = since if since_all is None else min(since_all, since)
        obs = store.load_timeline(pid, since=since, kinds={"observation"})
        inc = [e.id for e in store.load_timeline(pid, since=since, kinds={"incident"})]
        report = ta.analyze(pid, obs, inc, since, round_date)  # type: ignore[arg-type]
        abnormal = [line.dimension for line in report.lines if line.is_abnormal]
        profile = store.load_profile(pid)
        rows.append(
            {
                "patient_id": pid,
                "code_name": profile.code_name,
                "room": profile.room,
                "since": since.isoformat(),
                "abnormal_count": len(abnormal),
                "abnormal_dimensions": abnormal,
                "incident_count": len(inc),
                "reason": report.cross_dimension_signal
                or ("、".join(abnormal) if abnormal else "例行"),
            }
        )
    rows.sort(key=lambda r: (-(r["abnormal_count"] + r["incident_count"]), r["patient_id"]))
    return {
        "roster": rows,
        "since": (since_all or round_date - timedelta(days=30)).isoformat(),
        "round_date": round_date.isoformat(),
        "status": "roster_ready",
        "updated_at": now_iso(),
    }


def fan_out_trends(state: RoundState) -> list[Send]:
    return [
        Send(
            "trend_analyzer",
            {
                "patient_id": r["patient_id"],
                "since": r["since"],
                "until": state["round_date"],
                "thread_id": state.get("thread_id", ""),
            },
        )
        for r in state["roster"]
    ]


def trend_analyzer(task: PersonTask) -> Command:
    """Personal deep agent → trend_analyzer subagent → analyze_trends (traced, run id)."""
    from agents import personal

    pid = task["patient_id"]
    artifact, meta = personal.run_task(
        "trend", pid, thread_id=task.get("thread_id"), since=task["since"], until=task["until"]
    )
    report = TrendReport.model_validate(artifact)
    return Command(
        update={"trends": [report.model_dump(mode="json")], "agent_runs": [meta]},
        goto=Send(
            "familiarization_writer",
            {
                "patient_id": pid,
                "since": task["since"],
                "report": report.model_dump(mode="json"),
                "thread_id": task.get("thread_id"),
                "trend_meta": meta,
            },
        ),
    )


def familiarization_writer(task: PersonTask) -> dict[str, Any]:
    """Personal deep agent → familiarization_writer subagent writes the page (traced, run id)."""
    from agents import personal

    pid = task["patient_id"]
    artifact, meta = personal.run_task(
        "round_page", pid, thread_id=task.get("thread_id"), since=task["since"]
    )
    page = RoundPage.model_validate(artifact)
    assert page.status == "draft"
    page.agent_note = personal.agent_note(meta, task.get("trend_meta"))
    return {"round_pages": [page.model_dump(mode="json")], "agent_runs": [meta]}


def head_nurse_edit_list(state: RoundState) -> dict[str, Any]:
    decision = interrupt(
        {
            "type": "head_nurse_edit_list",
            "roster": state.get("roster", []),
            "round_pages": state.get("round_pages", []),
            "allowed_actions": ["publish"],
        }
    )
    return {
        "head_nurse_decision": decision,
        "review_log": [
            {
                "node": "head_nurse_edit_list",
                "action": "publish",
                "by": decision.get("head_nurse"),
                "ts": now_iso(),
            }
        ],
        "status": "list_edited",
        "updated_at": now_iso(),
    }


def publish_round_pages(state: RoundState) -> dict[str, Any]:
    decision = state.get("head_nurse_decision") or {}
    head = decision.get("head_nurse", "head_nurse")
    selected = set(
        decision.get("patient_ids") or [r["patient_id"] for r in state.get("roster", [])]
    )
    edits: dict[str, Any] = decision.get("edits") or {}
    store = get_store()
    published: list[str] = []
    for raw in state.get("round_pages", []):
        page = RoundPage.model_validate(raw)
        if page.patient_id not in selected:
            continue
        e = edits.get(page.patient_id) or {}
        if e.get("questions"):
            page.questions = list(e["questions"])
        if e.get("remove_dimensions"):
            page.changes = [
                c for c in page.changes if c.dimension not in set(e["remove_dimensions"])
            ]
        page.status = "approved"
        page.confirmed_by = head
        page.provenance = Provenance(
            source="nurse_confirmed",
            author="familiarization_writer",
            confirmed_by=head,
            ts=datetime.now(UTC),
        )
        store.write_document(page.patient_id, page)
        published.append(page.id)
    return {"published": published, "status": "published", "updated_at": now_iso()}


def doctor_round(state: RoundState) -> dict[str, Any]:
    """醫師看頁、看人、開醫囑 — the system does not intervene; it waits for typed orders."""
    decision = interrupt(
        {
            "type": "doctor_round",
            "published": state.get("published", []),
            "roster": state.get("roster", []),
            "allowed_actions": ["submit_orders"],
        }
    )
    return {
        "orders_input": decision.get("orders", []),
        "review_log": [
            {
                "node": "doctor_round",
                "action": "submit_orders",
                "by": decision.get("nurse_id"),
                "ts": now_iso(),
            }
        ],
        "head_nurse_decision": {
            **(state.get("head_nurse_decision") or {}),
            "order_nurse_id": decision.get("nurse_id", "nurse"),
        },
        "status": "orders_entered",
        "updated_at": now_iso(),
    }


def order_ingest(state: RoundState) -> dict[str, Any]:
    ts = datetime.now(UTC)
    nurse_id = (state.get("head_nurse_decision") or {}).get("order_nurse_id", "nurse")
    orders: list[dict[str, Any]] = []
    encounters: list[dict[str, Any]] = []
    for o in state.get("orders_input", []):
        pid = o["patient_id"]
        doctor = o.get("doctor", "doctor")
        enc_id = new_id("enc", ts)
        ord_id = new_id("ord", ts)
        prov = Provenance(source="doctor_ordered", author=doctor, confirmed_by=nurse_id, ts=ts)
        items = doctor_order.parse_order(o["text"])
        orders.append(
            Order(
                id=ord_id,
                patient_id=pid,
                ts=ts,
                status="draft",
                provenance=prov,
                doctor=doctor,
                raw_text=o["text"],
                items=items,
                encounter_id=enc_id,
            ).model_dump(mode="json")
        )
        encounters.append(
            Encounter(
                id=enc_id,
                patient_id=pid,
                ts=ts,
                status="draft",
                provenance=prov,
                encounter_type="round",
                doctor=doctor,
                summary=f"巡診：{o['text'][:60]}",
                order_ids=[ord_id],
            ).model_dump(mode="json")
        )
    return {
        "orders": orders,
        "encounters": encounters,
        "status": "orders_ingested",
        "updated_at": now_iso(),
    }


def order_to_caregiver_notes(state: RoundState) -> dict[str, Any]:
    store = get_store()
    ts = datetime.now(UTC)
    notes: list[dict[str, Any]] = []
    for raw in state.get("orders", []):
        order = Order.model_validate(raw)
        profile = store.load_profile(order.patient_id)
        items = get_llm().caregiver_notes(order.raw_text, profile)
        if not items:
            continue
        items_zh = items
        lang = profile.caregiver_language
        notes.append(
            CaregiverNotes(
                id=new_id("notes", ts),
                patient_id=order.patient_id,
                generated_at=ts,
                generated_from=[order.id],
                status="draft",
                author="order_ingest",
                provenance=Provenance(source="doctor_ordered", author="order_ingest", ts=ts),
                audience="caregiver",
                lang=lang,
                items=items,
                items_zh=items_zh,
                source_order_id=order.id,
            ).model_dump(mode="json")
        )
    return {"caregiver_notes": notes}  # parallel with baseline_update_proposal: no shared keys


def baseline_update_proposal(state: RoundState) -> dict[str, Any]:
    store = get_store()
    ts = datetime.now(UTC)
    proposals: list[dict[str, Any]] = []
    for raw in state.get("orders", []):
        order = Order.model_validate(raw)
        baseline = store.load_baseline(order.patient_id)
        entries: list[BaselineEntry] = []
        for item in order.items:
            if item.target_dimension and item.category in (
                "diet",
                "activity",
                "medication",
                "observation",
            ):
                cur = baseline.current(item.target_dimension, on=ts.date())
                entries.append(
                    BaselineEntry(
                        dimension=item.target_dimension,
                        value=cur.value if cur else None,
                        description=(
                            f"{cur.description if cur else '（無基線）'}；"
                            f"{ts.date()} 醫囑後觀察：{item.text}"
                        ),
                        valid_from=ts.date(),
                        set_by="doctor_ordered",
                        provenance=Provenance(source="doctor_ordered", author=order.doctor, ts=ts),
                    )
                )
        if entries:
            proposals.append(
                BaselineProposal(
                    patient_id=order.patient_id,
                    proposals=entries,
                    reason=f"醫囑 {order.id}",
                    status="draft",
                    source_order_id=order.id,
                ).model_dump(mode="json")
            )
    return {"baseline_proposals": proposals, "status": "baseline_proposed", "updated_at": now_iso()}


def nurse_confirm_baseline(state: RoundState) -> dict[str, Any]:
    decision = interrupt(
        {
            "type": "nurse_confirm_baseline",
            "proposals": state.get("baseline_proposals", []),
            "allowed_actions": ["approve", "reject"],
        }
    )
    return {
        "baseline_decision": decision,
        "review_log": [
            {
                "node": "nurse_confirm_baseline",
                "action": decision.get("action"),
                "by": decision.get("nurse_id"),
                "ts": now_iso(),
            }
        ],
        "status": "baseline_decided",
        "updated_at": now_iso(),
    }


def baseline_write(state: RoundState) -> dict[str, Any]:
    decision = state.get("baseline_decision") or {}
    if decision.get("action") != "approve":
        return {"baseline_written": [], "status": "baseline_rejected", "updated_at": now_iso()}
    nurse_id = decision.get("nurse_id", "nurse")
    accepted: dict[str, list[str]] | None = decision.get("accepted")
    store = get_store()
    written: list[str] = []
    for raw in state.get("baseline_proposals", []):
        prop = BaselineProposal.model_validate(raw)
        if accepted is not None:
            dims = set(accepted.get(prop.patient_id, []))
            prop.proposals = [e for e in prop.proposals if e.dimension in dims]
        if not prop.proposals:
            continue
        prop.status = "approved"
        prop.confirmed_by = nurse_id
        store.write_baseline(prop.patient_id, prop)
        written.extend(f"{prop.patient_id}:{e.dimension}" for e in prop.proposals)
    return {"baseline_written": written, "status": "baseline_written", "updated_at": now_iso()}


def round_timeline_write(state: RoundState) -> dict[str, Any]:
    store = get_store()
    nurse_id = (state.get("head_nurse_decision") or {}).get("order_nurse_id", "nurse")
    ids: list[str] = []
    for raw in state.get("encounters", []) + state.get("orders", []):
        entry = (
            Encounter.model_validate(raw)
            if raw["kind"] == "encounter"
            else Order.model_validate(raw)
        )
        entry.status = "approved"
        entry.confirmed_by = nurse_id
        assert entry.status == "approved" and entry.confirmed_by, "timeline_write requires approval"
        ids.append(guarded_timeline_write(entry.patient_id, entry))
    for raw in state.get("caregiver_notes", []):
        doc = CaregiverNotes.model_validate(raw)
        doc.status = "approved"
        doc.confirmed_by = nurse_id
        store.write_document(doc.patient_id, doc)
        ids.append(doc.id)
    return {"written_ids": ids, "status": "done", "deadline": None, "updated_at": now_iso()}


def build_round_graph() -> StateGraph:
    g = StateGraph(RoundState)
    g.add_node("roster_agent", roster_agent)
    g.add_node("trend_analyzer", trend_analyzer, destinations=("familiarization_writer",))
    g.add_node("familiarization_writer", familiarization_writer)
    g.add_node("head_nurse_edit_list", head_nurse_edit_list)
    g.add_node("publish_round_pages", publish_round_pages)
    g.add_node("doctor_round", doctor_round)
    g.add_node("order_ingest", order_ingest)
    g.add_node("order_to_caregiver_notes", order_to_caregiver_notes)
    g.add_node("baseline_update_proposal", baseline_update_proposal)
    g.add_node("nurse_confirm_baseline", nurse_confirm_baseline)
    g.add_node("baseline_write", baseline_write)
    g.add_node("timeline_write", round_timeline_write)
    g.add_edge(START, "roster_agent")
    g.add_conditional_edges("roster_agent", fan_out_trends, ["trend_analyzer"])
    g.add_edge("familiarization_writer", "head_nurse_edit_list")
    g.add_edge("head_nurse_edit_list", "publish_round_pages")
    g.add_edge("publish_round_pages", "doctor_round")
    g.add_edge("doctor_round", "order_ingest")
    g.add_edge("order_ingest", "order_to_caregiver_notes")
    g.add_edge("order_ingest", "baseline_update_proposal")
    g.add_edge("baseline_update_proposal", "nurse_confirm_baseline")
    g.add_edge("nurse_confirm_baseline", "baseline_write")
    g.add_edge(["order_to_caregiver_notes", "baseline_write"], "timeline_write")
    g.add_edge("timeline_write", END)
    return g


# Names used by the mermaid diagrams (kept in one place so a test can diff them).
SHIFT_NODES = (
    "load_person_record",
    "intake_agent",
    "baseline_comparator",
    "red_flag_rules",
    "notify_nurse_urgent",
    "to_path_a",
    "minimal_sbar_draft",
    "nurse_10s_confirm",
    "timeline_write",
    "timeline_curator",
)
ROUND_NODES = (
    "roster_agent",
    "trend_analyzer",
    "familiarization_writer",
    "head_nurse_edit_list",
    "publish_round_pages",
    "doctor_round",
    "order_ingest",
    "order_to_caregiver_notes",
    "baseline_update_proposal",
    "nurse_confirm_baseline",
    "baseline_write",
    "timeline_write",
)
