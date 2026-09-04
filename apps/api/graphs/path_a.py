"""Path A — 急症（需看醫師，不到 119）. Node names == docs/langgraph_path_a_incident.mermaid.

◇ interrupts: nurse_review, nurse_route_choice, nurse_approve_notification
(+ nurse_onsite_assessment interrupts only on the red-flag path, where no review happened).
"""

from __future__ import annotations

import logging
import operator
from datetime import UTC, datetime, timedelta
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt
from record_schema import (
    ISBAR,
    Baseline,
    BaselineDelta,
    CaregiverSection,
    FollowUp,
    Incident,
    IncidentFile,
    Notification,
    NurseSection,
    OnsiteAssessment,
    Profile,
    Provenance,
    RedFlagResult,
    StructuredObservation,
    Vitals,
)

from agents.subagents import handoff_packager as handoff_packager_mod
from core.ids import new_id
from core.llm import get_llm
from core.settings import get_settings
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
from record.store import get_store
from red_flags.rules import RedFlagInput, evaluate

log = logging.getLogger(__name__)

ROUTE_LABELS = {
    "contact_contract_hospital": "聯絡特約醫療機構",
    "home_acute_mode_b": "在宅急症照護模式 B",
    "accompany_visit": "安排陪同就醫",
    "observe": "轉為觀察（進入每班流程）",
    "escalate_119": "119 後送",
}


class PathAState(TypedDict, total=False):
    patient_id: str
    thread_id: str
    path: str
    raw_input: dict[str, Any]
    caregiver_addendum: str | None
    profile: dict[str, Any]
    baseline: dict[str, Any]
    recent_lines: list[str]
    recent_observations: list[dict[str, Any]]
    structured_observation: dict[str, Any]
    baseline_delta: list[dict[str, Any]]
    red_flags: dict[str, Any]
    caregiver_section: dict[str, Any]
    sbar: dict[str, Any]
    nurse_section: dict[str, Any]
    review_decision: dict[str, Any]
    route_decision: str
    documents: dict[str, Any]
    incident_entry: dict[str, Any]
    incident_file: dict[str, Any]
    family_notification: dict[str, Any]
    follow_up: dict[str, Any]
    notifications: Annotated[list[dict[str, Any]], operator.add]
    provenance: Annotated[list[dict[str, Any]], operator.add]
    review_log: Annotated[list[dict[str, Any]], operator.add]
    status: str
    deadline: str | None
    escalation_level: int
    updated_at: str


# --- helpers ---------------------------------------------------------------------------------


def _obs(state: dict[str, Any]) -> StructuredObservation:
    return StructuredObservation.model_validate(state["structured_observation"])


def _deltas(state: dict[str, Any]) -> list[BaselineDelta]:
    return [BaselineDelta.model_validate(d) for d in state.get("baseline_delta", [])]


def _prov_line(
    ref: str, source: str, author: str, confirmed_by: str | None = None
) -> dict[str, Any]:
    return {
        "line_id": new_id("prov"),
        "ref": ref,
        "field": "",
        "source": source,
        "author": author,
        "confirmed_by": confirmed_by,
        "ts": now_iso(),
        "language_original": "zh-TW",
    }


def isbar_skeleton(
    profile: Profile,
    baseline: Baseline,
    obs: StructuredObservation,
    deltas: list[BaselineDelta],
    recent_lines: list[str],
) -> ISBAR:
    """Red-flag path: no AI draft was made; I/S/B come from facts, A/R are left to the nurse."""
    draft = get_llm().draft_isbar(profile, baseline, obs, deltas, recent_lines)
    draft.author = "nurse"
    return draft


def compile_incident(
    *,
    profile: Profile,
    obs: StructuredObservation,
    caregiver_section: CaregiverSection,
    nurse_section: NurseSection,
    red_flags: RedFlagResult | None,
    route: str,
    nurse_id: str,
    ts: datetime,
    generated_from: list[str],
    incident_kind: str | None = None,
) -> tuple[Incident, IncidentFile]:
    kind = incident_kind or (obs.incident_flags[0] if obs.incident_flags else "acute")
    summary = nurse_section.isbar.situation[:120]
    inc_id = new_id("inc", ts)
    file_id = new_id("incfile", ts)
    prov = Provenance(source="nurse_confirmed", author=nurse_id, confirmed_by=nurse_id, ts=ts)
    entry = Incident(
        id=inc_id,
        patient_id=profile.patient_id,
        ts=ts,
        status="approved",
        confirmed_by=nurse_id,
        provenance=prov,
        related_ids=generated_from,
        incident_kind=kind,  # type: ignore[arg-type]
        summary=summary,
        incident_file_id=file_id,
    )
    doc = IncidentFile(
        id=file_id,
        patient_id=profile.patient_id,
        generated_at=ts,
        generated_from=[inc_id, *generated_from],
        status="approved",
        author="incident_compiler",
        confirmed_by=nurse_id,
        provenance=prov,
        audience="nurse",
        caregiver_section=caregiver_section,
        nurse_section=nurse_section,
        red_flags=red_flags,
        route_decision=route,  # type: ignore[arg-type]
        notifications=[],
    )
    return entry, doc


# --- nodes -----------------------------------------------------------------------------------


def caregiver_section_writer(state: PathAState) -> dict[str, Any]:
    obs = _obs(state)
    raw = state["raw_input"]
    profile = Profile.model_validate(state["profile"])
    cs = CaregiverSection(
        raw_text=obs.raw_text,
        language=obs.language,
        translation_zh=obs.translation_zh,
        domains=obs.domains,
        seems_different=obs.seems_different,
        incident_flags=obs.incident_flags,
        followups=obs.followups,
        unknown=obs.unknown,
        image_summary="影像摘要（固定 mock）：已附照片，請護理師現場確認。"
        if raw.get("media_refs")
        else None,
        caregiver_confirmed_meaning=raw.get("caregiver_confirmed_meaning"),
        provenance=Provenance(
            source="caregiver_said",
            author=raw.get("caregiver_id") or profile.caregiver_code_name,
            ts=datetime.now(UTC),
            language_original=obs.language,
        ),
    )
    return {
        "caregiver_section": cs.model_dump(mode="json"),
        "provenance": [_prov_line("caregiver_section", "caregiver_said", cs.provenance.author)],
        "status": "caregiver_section_ready",
        "updated_at": now_iso(),
    }


def sbar_draft(state: PathAState) -> dict[str, Any]:
    profile = Profile.model_validate(state["profile"])
    baseline = Baseline.model_validate(state["baseline"])
    draft = get_llm().draft_isbar(
        profile, baseline, _obs(state), _deltas(state), state.get("recent_lines", [])
    )
    assert draft.status == "draft" and draft.author == "ai"
    assert draft.nurse_assessment is None and draft.nurse_recommendation is None
    return {
        "sbar": draft.model_dump(mode="json"),
        "provenance": [_prov_line("sbar", "ai_extracted", "nurse_assist")],
        "status": "sbar_drafted",
        "updated_at": now_iso(),
    }


def push_to_nurse(state: PathAState) -> dict[str, Any]:
    profile = Profile.model_validate(state["profile"])
    note = {
        "to": "nurse",
        "channel": "screen",
        "content": f"{profile.code_name}（{profile.room}）有一份 ISBAR 草稿待審核",
        "status": "displayed_only",
        "sent_at": now_iso(),
    }
    return {
        "notifications": [note],
        "deadline": deadline_iso(),
        "status": "awaiting_nurse_review",
        "updated_at": now_iso(),
    }


def nurse_review(state: PathAState) -> dict[str, Any]:
    payload = {
        "type": "nurse_review",
        "patient_id": state["patient_id"],
        "sbar": state.get("sbar"),
        "caregiver_section": state.get("caregiver_section"),
        "baseline_delta": state.get("baseline_delta", []),
        "red_flags": state.get("red_flags"),
        "deadline": state.get("deadline"),
        "escalation_level": state.get("escalation_level", 0),
        "allowed_actions": ["accept", "edit", "return", "escalate"],
    }
    decision = interrupt(payload)
    action = decision.get("action", "accept")
    entry = {
        "node": "nurse_review",
        "action": action,
        "by": decision.get("nurse_id", "unknown"),
        "ts": now_iso(),
        "reason": decision.get("return_reason"),
    }
    update: dict[str, Any] = {
        "review_decision": decision,
        "review_log": [entry],
        "updated_at": now_iso(),
    }
    if action == "return":
        update["caregiver_addendum"] = decision.get("caregiver_addendum")
        update["status"] = "returned_to_intake"
        update["deadline"] = None
    elif action == "escalate":
        update["status"] = "escalating"
    else:
        update["status"] = "nurse_accepted"
        update["deadline"] = None
    return update


def route_after_review(state: PathAState) -> str:
    action = (state.get("review_decision") or {}).get("action", "accept")
    return {"return": "intake_agent", "escalate": "escalate"}.get(action, "nurse_onsite_assessment")


def escalate(state: PathAState) -> dict[str, Any]:
    level = state.get("escalation_level", 0) + 1
    to = "second_nurse" if level == 1 else "head_nurse"
    profile = Profile.model_validate(state["profile"])
    note = {
        "to": to,
        "channel": "screen",
        "content": (
            f"{profile.code_name}（{profile.room}）ISBAR 審核逾時，"
            f"第 {level} 次升級通知{'第二護理師' if level == 1 else '護理長'}"
        ),
        "status": "displayed_only",
        "sent_at": now_iso(),
    }
    return {
        "escalation_level": level,
        "notifications": [note],
        "deadline": deadline_iso(),
        "status": "awaiting_nurse_review",
        "updated_at": now_iso(),
    }


def nurse_onsite_assessment(state: PathAState) -> dict[str, Any]:
    decision = state.get("review_decision") or {}
    if not decision.get("onsite_assessment"):
        # red-flag path: nothing was drafted; the nurse assesses first, then the ISBAR exists.
        decision = interrupt(
            {
                "type": "nurse_onsite_assessment",
                "patient_id": state["patient_id"],
                "red_flags": state.get("red_flags"),
                "structured_observation": state.get("structured_observation"),
                "baseline_delta": state.get("baseline_delta", []),
                "allowed_actions": ["confirm"],
            }
        )
    profile = Profile.model_validate(state["profile"])
    baseline = Baseline.model_validate(state["baseline"])
    obs = _obs(state)
    deltas = _deltas(state)
    nurse_id = decision.get("nurse_id", "nurse")
    oa_in = decision.get("onsite_assessment") or {}
    ts = datetime.now(UTC)
    oa = OnsiteAssessment(
        vitals=Vitals(**{**(oa_in.get("vitals") or {}), "measured_by": nurse_id, "ts": ts}),
        consciousness=oa_in.get("consciousness", ""),
        wound=oa_in.get("wound"),
        notes=oa_in.get("notes"),
        assessed_by=nurse_id,
        ts=ts,
    )
    sbar = (
        ISBAR.model_validate(state["sbar"])
        if state.get("sbar")
        else isbar_skeleton(profile, baseline, obs, deltas, state.get("recent_lines", []))
    )
    edits = decision.get("edits") or {}
    if edits.get("situation"):
        sbar.situation = edits["situation"]
    if edits.get("background"):
        sbar.background = edits["background"]
    sbar.nurse_assessment = decision.get("nurse_assessment") or None
    sbar.nurse_recommendation = decision.get("nurse_recommendation") or None
    sbar.author = "nurse"
    result = evaluate(
        RedFlagInput(
            observation=obs,
            vitals=oa.vitals,
            baseline_vitals=baseline.vitals_usual,
            on_anticoagulant=profile.on_anticoagulant,
        )
    )
    ns = NurseSection(onsite_assessment=oa, isbar=sbar)
    return {
        "review_decision": decision,
        "sbar": sbar.model_dump(mode="json"),
        "nurse_section": ns.model_dump(mode="json"),
        "red_flags": result.model_dump(mode="json"),
        "provenance": [_prov_line("nurse_section.onsite_assessment", "nurse_assessed", nurse_id)],
        "status": "onsite_done",
        "deadline": None,
        "updated_at": now_iso(),
    }


def sbar_final(state: PathAState) -> dict[str, Any]:
    sbar = ISBAR.model_validate(state["sbar"])
    nurse_id = (state.get("review_decision") or {}).get("nurse_id", "nurse")
    assert sbar.nurse_assessment, "ISBAR A 由護理師撰寫，不可空白"
    assert sbar.nurse_recommendation, "ISBAR R 由護理師撰寫，不可空白"
    ts = datetime.now(UTC)
    sbar.status = "approved"
    sbar.author = "nurse"
    sbar.confirmed_by = nurse_id
    sbar.confirmed_at = ts
    ns = NurseSection.model_validate(state["nurse_section"])
    ns.isbar = sbar
    ns.confirmed_by = nurse_id
    ns.confirmed_at = ts
    return {
        "sbar": sbar.model_dump(mode="json"),
        "nurse_section": ns.model_dump(mode="json"),
        "provenance": [_prov_line("sbar", "nurse_confirmed", nurse_id, nurse_id)],
        "status": "sbar_final",
        "updated_at": now_iso(),
    }


def nurse_route_choice(state: PathAState) -> dict[str, Any]:
    decision = interrupt(
        {
            "type": "nurse_route_choice",
            "patient_id": state["patient_id"],
            "sbar": state.get("sbar"),
            "options": ROUTE_LABELS,
            "allowed_actions": list(ROUTE_LABELS),
        }
    )
    route = decision.get("route", "observe")
    assert route in ROUTE_LABELS, f"unknown route {route}"
    return {
        "route_decision": route,
        "review_log": [
            {
                "node": "nurse_route_choice",
                "action": route,
                "by": decision.get("nurse_id"),
                "ts": now_iso(),
            }
        ],
        "status": "routed",
        "updated_at": now_iso(),
    }


def route_after_choice(state: PathAState) -> str:
    return "to_routine_timeline" if state.get("route_decision") == "observe" else "handoff_packager"


def _generated_from(state: PathAState) -> list[str]:
    return [o["id"] for o in state.get("recent_observations", [])][-6:]


def handoff_packager(state: PathAState) -> dict[str, Any]:
    profile = Profile.model_validate(state["profile"])
    baseline = Baseline.model_validate(state["baseline"])
    sbar = ISBAR.model_validate(state["sbar"])
    nurse_id = sbar.confirmed_by or "nurse"
    page = handoff_packager_pkg(
        profile, baseline, sbar, _generated_from(state), state["route_decision"], nurse_id
    )
    docs = dict(state.get("documents") or {})
    docs["handoff_page"] = page.model_dump(mode="json")
    return {"documents": docs, "status": "handoff_packaged", "updated_at": now_iso()}


def handoff_packager_pkg(profile, baseline, sbar, generated_from, route, nurse_id):
    return handoff_packager_mod.package(
        profile,
        baseline,
        sbar,
        generated_from,
        route,
        nurse_id,  # type: ignore[arg-type]
    )


def to_routine_timeline(state: PathAState) -> dict[str, Any]:
    docs = dict(state.get("documents") or {})
    docs["routine_note"] = "護理師決定轉為觀察：後續由 Path B 每班流程持續追蹤。"
    return {"documents": docs, "status": "to_routine", "updated_at": now_iso()}


def incident_compiler(state: PathAState) -> dict[str, Any]:
    profile = Profile.model_validate(state["profile"])
    obs = _obs(state)
    cs = (
        CaregiverSection.model_validate(state["caregiver_section"])
        if state.get("caregiver_section")
        else None
    )
    if cs is None:  # red-flag path skipped caregiver_section_writer; compile it from facts now
        cs = CaregiverSection.model_validate(caregiver_section_writer(state)["caregiver_section"])
    ns = NurseSection.model_validate(state["nurse_section"])
    rf = RedFlagResult.model_validate(state["red_flags"]) if state.get("red_flags") else None
    nurse_id = ns.confirmed_by or "nurse"
    entry, doc = compile_incident(
        profile=profile,
        obs=obs,
        caregiver_section=cs,
        nurse_section=ns,
        red_flags=rf,
        route=state["route_decision"],
        nurse_id=nurse_id,
        ts=datetime.now(UTC),
        generated_from=_generated_from(state),
    )
    return {
        "incident_entry": entry.model_dump(mode="json"),
        "incident_file": doc.model_dump(mode="json"),
        "status": "incident_compiled",
        "updated_at": now_iso(),
    }


def timeline_write(state: PathAState) -> dict[str, Any]:
    payload = Incident.model_validate(state["incident_entry"])
    assert payload.status == "approved" and payload.confirmed_by, "timeline_write requires approval"
    pid = state["patient_id"]
    store = get_store()
    inc_id = guarded_timeline_write(pid, payload)
    doc = IncidentFile.model_validate(state["incident_file"])
    store.write_document(pid, doc)
    docs = dict(state.get("documents") or {})
    docs["incident_file"] = doc.id
    docs["incident_entry"] = inc_id
    if docs.get("handoff_page"):
        from record_schema import HandoffPage

        hp = HandoffPage.model_validate(docs["handoff_page"])
        store.write_document(pid, hp)
        docs["handoff_page_id"] = hp.id
    return {
        "documents": docs,
        "provenance": [
            _prov_line(
                inc_id, "nurse_confirmed", payload.confirmed_by or "nurse", payload.confirmed_by
            )
        ],
        "status": "written",
        "updated_at": now_iso(),
    }


def family_notification_draft(state: PathAState) -> dict[str, Any]:
    profile = Profile.model_validate(state["profile"])
    sbar = ISBAR.model_validate(state["sbar"])
    obs = _obs(state)
    what = "、".join(f"「{dv.raw_quote}」" for dv in obs.domains.values()) or f"「{obs.raw_text}」"
    what = f"照護者回報{what}"
    route_text = ROUTE_LABELS.get(state.get("route_decision", "observe"), "持續觀察")
    text = get_llm().family_notification(profile, what, route_text)
    draft = Notification(to="family", channel="line", content=text, status="draft")
    _ = sbar
    return {
        "family_notification": draft.model_dump(mode="json"),
        "status": "family_draft",
        "updated_at": now_iso(),
    }


def nurse_approve_notification(state: PathAState) -> dict[str, Any]:
    decision = interrupt(
        {
            "type": "nurse_approve_notification",
            "patient_id": state["patient_id"],
            "draft": state.get("family_notification"),
            "allowed_actions": ["approve", "edit", "skip"],
        }
    )
    fam = Notification.model_validate(state["family_notification"])
    action = decision.get("action", "approve")
    if action == "skip":
        fam.status = "draft"
        fam.content = fam.content
        status = "family_skipped"
    else:
        if action == "edit" and decision.get("content"):
            fam.content = decision["content"]
        fam.status = "approved"
        fam.approved_by = decision.get("nurse_id", "nurse")
        status = "family_approved"
    return {
        "family_notification": fam.model_dump(mode="json"),
        "review_log": [
            {
                "node": "nurse_approve_notification",
                "action": action,
                "by": decision.get("nurse_id"),
                "ts": now_iso(),
            }
        ],
        "status": status,
        "updated_at": now_iso(),
    }


def send_line(state: PathAState) -> dict[str, Any]:
    fam = Notification.model_validate(state["family_notification"])
    s = get_settings()
    if fam.status == "approved":
        if s.LINE_CHANNEL_TOKEN and s.LINE_FAMILY_TO:
            try:
                import httpx

                r = httpx.post(
                    "https://api.line.me/v2/bot/message/push",
                    headers={"Authorization": f"Bearer {s.LINE_CHANNEL_TOKEN}"},
                    json={
                        "to": s.LINE_FAMILY_TO,
                        "messages": [{"type": "text", "text": fam.content}],
                    },
                    timeout=10,
                )
                fam.status = "sent" if r.status_code == 200 else "displayed_only"
            except Exception as e:  # noqa: BLE001
                log.warning("LINE push failed: %s", e)
                fam.status = "displayed_only"
        else:
            fam.status = "displayed_only"
        fam.sent_at = datetime.now(UTC)
    else:
        fam.status = "displayed_only"
    pid = state["patient_id"]
    store = get_store()
    doc = store.get_document(pid, state["documents"]["incident_file"])
    if doc is not None and doc.doc_type == "incident_file":
        doc.notifications = [*doc.notifications, fam]
        store.update_document(pid, doc)
    return {
        "family_notification": fam.model_dump(mode="json"),
        "notifications": [fam.model_dump(mode="json")],
        "status": "line_" + fam.status,
        "updated_at": now_iso(),
    }


def schedule_follow_up(state: PathAState) -> dict[str, Any]:
    profile = Profile.model_validate(state["profile"])
    hours = int((state.get("review_decision") or {}).get("follow_up_hours", 4))
    q = {
        "zh-TW": "他現在怎麼樣？有比較好嗎？",
        "id": "Bagaimana keadaannya sekarang? Sudah lebih baik?",
        "vi": "Bây giờ ông/bà thế nào? Đỡ hơn chưa?",
        "en": "How are they now? Any better?",
    }.get(profile.caregiver_language, "他現在怎麼樣？")
    nurse_id = (state.get("review_decision") or {}).get("nurse_id", "nurse")
    fu = FollowUp(due_at=datetime.now(UTC) + timedelta(hours=hours), question=q, set_by=nurse_id)
    pid = state["patient_id"]
    store = get_store()
    doc = store.get_document(pid, state["documents"]["incident_file"])
    if doc is not None and doc.doc_type == "incident_file":
        doc.follow_up = fu
        store.update_document(pid, doc)
    return {
        "follow_up": fu.model_dump(mode="json"),
        "status": "done",
        "deadline": None,
        "updated_at": now_iso(),
    }


# --- graph -----------------------------------------------------------------------------------


def build_path_a() -> StateGraph:
    g = StateGraph(PathAState)
    for fn in (
        load_person_record,
        intake_agent,
        baseline_comparator,
        red_flag_rules,
        notify_nurse_urgent,
        caregiver_section_writer,
        sbar_draft,
        push_to_nurse,
        nurse_review,
        escalate,
        nurse_onsite_assessment,
        sbar_final,
        nurse_route_choice,
        handoff_packager,
        to_routine_timeline,
        incident_compiler,
        timeline_write,
        family_notification_draft,
        nurse_approve_notification,
        send_line,
        schedule_follow_up,
    ):
        g.add_node(fn.__name__, fn)
    g.add_edge(START, "load_person_record")
    g.add_edge("load_person_record", "intake_agent")
    g.add_edge("intake_agent", "baseline_comparator")
    g.add_edge("baseline_comparator", "red_flag_rules")
    g.add_conditional_edges(
        "red_flag_rules",
        lambda s: "notify_nurse_urgent" if red_flag_hit(s) else "caregiver_section_writer",
        ["notify_nurse_urgent", "caregiver_section_writer"],
    )
    g.add_edge("notify_nurse_urgent", "nurse_onsite_assessment")
    g.add_edge("caregiver_section_writer", "sbar_draft")
    g.add_edge("sbar_draft", "push_to_nurse")
    g.add_edge("push_to_nurse", "nurse_review")
    g.add_conditional_edges(
        "nurse_review", route_after_review, ["intake_agent", "escalate", "nurse_onsite_assessment"]
    )
    g.add_edge("escalate", "nurse_review")
    g.add_edge("nurse_onsite_assessment", "sbar_final")
    g.add_edge("sbar_final", "nurse_route_choice")
    g.add_conditional_edges(
        "nurse_route_choice", route_after_choice, ["handoff_packager", "to_routine_timeline"]
    )
    g.add_edge("handoff_packager", "incident_compiler")
    g.add_edge("to_routine_timeline", "incident_compiler")
    g.add_edge("incident_compiler", "timeline_write")
    g.add_edge("timeline_write", "family_notification_draft")
    g.add_edge("family_notification_draft", "nurse_approve_notification")
    g.add_edge("nurse_approve_notification", "send_line")
    g.add_edge("send_line", "schedule_follow_up")
    g.add_edge("schedule_follow_up", END)
    return g


INTERRUPT_NODES = (
    "nurse_review",
    "nurse_route_choice",
    "nurse_approve_notification",
    "nurse_onsite_assessment",
)
