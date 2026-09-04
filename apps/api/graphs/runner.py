"""Start / resume / inspect graph threads. thread_id = f"{patient_id}:{graph}:{date}" (+ suffix)."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from functools import lru_cache
from typing import Any

from langgraph.types import Command

from core.trace import tagged
from graphs import registry
from graphs.checkpointer import get_checkpointer
from graphs.path_a import build_path_a
from graphs.path_b import build_round_graph, build_shift_graph

log = logging.getLogger(__name__)

BUILDERS = {"path_a": build_path_a, "shift": build_shift_graph, "round": build_round_graph}

REQUIRED_RESUME_FIELDS: dict[str, list[str]] = {
    "nurse_review": ["action", "nurse_id"],
    "nurse_onsite_assessment": [
        "nurse_id",
        "onsite_assessment",
        "nurse_assessment",
        "nurse_recommendation",
    ],
    "nurse_route_choice": ["route", "nurse_id"],
    "nurse_approve_notification": ["action", "nurse_id"],
    "nurse_10s_confirm": ["action", "nurse_id"],
    "head_nurse_edit_list": ["head_nurse"],
    "doctor_round": ["orders", "nurse_id"],
    "nurse_confirm_baseline": ["action", "nurse_id"],
}


@lru_cache
def compiled(graph: str):
    return BUILDERS[graph]().compile(checkpointer=get_checkpointer())


def _config(thread_id: str) -> dict[str, Any]:
    cfg: dict[str, Any] = {"configurable": {"thread_id": thread_id}}
    if graph_of(thread_id) == "round":
        # trend_analyzer ×N / familiarization_writer ×N run one resident at a time: each is a
        # deep-agent run with several model calls, and parallel runs trip the provider TPM limit.
        cfg["max_concurrency"] = 1
    return cfg


def graph_of(thread_id: str) -> str:
    return thread_id.split(":")[1]


def new_thread_id(graph: str, patient_id: str, on: datetime | None = None) -> str:
    on = on or datetime.now(UTC)
    base = f"{patient_id}:{graph}:{on.date().isoformat()}"
    tid, n = base, 1
    while registry.get(tid) is not None:
        n += 1
        tid = f"{base}:{n}"
    return tid


def snapshot(thread_id: str) -> dict[str, Any]:
    graph = graph_of(thread_id)
    st = compiled(graph).get_state(_config(thread_id))
    interrupts = [i for t in st.tasks for i in t.interrupts]
    values = dict(st.values or {})
    status = "done" if not st.next else ("interrupted" if interrupts else "running")
    interrupt_payload = interrupts[0].value if interrupts else None
    deadline = values.get("deadline")
    dl = datetime.fromisoformat(deadline) if isinstance(deadline, str) else None
    registry.upsert(
        thread_id,
        graph=graph,
        patient_id=values.get("patient_id", "ALL"),
        status=status,
        interrupt_type=(interrupt_payload or {}).get("type") if interrupt_payload else None,
        deadline=dl,
        escalation_level=values.get("escalation_level", 0),
    )
    return {
        "thread_id": thread_id,
        "graph": graph,
        "status": status,
        "next": list(st.next),
        "interrupt": interrupt_payload,
        "values": values,
    }


def start(graph: str, patient_id: str, input_values: dict[str, Any]) -> dict[str, Any]:
    tid = new_thread_id(graph, patient_id)
    registry.upsert(tid, graph=graph, patient_id=patient_id, status="running")
    compiled(graph).invoke(
        {**input_values, "patient_id": patient_id, "thread_id": tid}, _config(tid)
    )
    return snapshot(tid)


def validate_resume(interrupt_type: str | None, payload: dict[str, Any]) -> None:
    if not interrupt_type:
        raise ValueError("thread is not waiting for input")
    missing = [f for f in REQUIRED_RESUME_FIELDS.get(interrupt_type, []) if not payload.get(f)]
    if payload.get("action") in ("return", "escalate", "skip", "reject") and interrupt_type in (
        "nurse_review",
        "nurse_approve_notification",
        "nurse_10s_confirm",
        "nurse_confirm_baseline",
    ):
        missing = [m for m in missing if m in ("action", "nurse_id")]
    if interrupt_type == "nurse_review" and payload.get("action") in ("accept", "edit"):
        for f in ("onsite_assessment", "nurse_assessment", "nurse_recommendation"):
            if not payload.get(f):
                missing.append(f)
    if missing:
        raise ValueError(f"{interrupt_type} resume is missing: {', '.join(missing)}")


def resume(thread_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    snap = snapshot(thread_id)
    itype = (snap["interrupt"] or {}).get("type") if snap["interrupt"] else None
    validate_resume(itype, payload)
    dialog_id = (snap["values"].get("raw_input") or {}).get("dialog_id")
    with tagged(thread_id=thread_id, dialog_id=dialog_id):
        compiled(graph_of(thread_id)).invoke(Command(resume=payload), _config(thread_id))
    return snapshot(thread_id)


def reset_for_tests() -> None:
    compiled.cache_clear()
    registry.reset_for_tests()


LIVE_REPORT_NODES = {
    "nurse_onsite_assessment": "notify_nurse_urgent",
    "nurse_review": "push_to_nurse",
}


def update_caregiver(
    thread_id: str, turns: list[dict[str, Any]], incidents: list[str], seems_different: bool
) -> dict[str, Any]:
    """Caregiver keeps answering while the nurse is on the way: merge the answers into the
    interrupted Path A thread (update_state as the node before the interrupt, then re-arm it)."""
    from datetime import UTC, datetime

    from record_schema import Baseline, Observation, Profile

    from agents.comparator import compare
    from graphs.common import build_caregiver_section, now_iso
    from ingest.intake_dialog import Turn, run_dialog
    from record.store import get_store
    from red_flags.rules import RedFlagInput, evaluate

    snap = snapshot(thread_id)
    itype = (snap["interrupt"] or {}).get("type") if snap["interrupt"] else None
    if snap["status"] != "interrupted" or itype not in LIVE_REPORT_NODES:
        raise ValueError("護理師已接手")
    g = compiled(graph_of(thread_id))
    values = snap["values"]
    store = get_store()
    pid = values["patient_id"]
    profile = store.load_profile(pid)
    baseline = store.load_baseline(pid)
    dialog_id = (values.get("raw_input") or {}).get("dialog_id")
    res = run_dialog(
        [Turn.model_validate(x) for x in turns],
        profile,
        baseline,
        seems_different=seems_different,
        incidents=incidents,
    )
    obs = res.observation
    recent = [Observation.model_validate(o) for o in values.get("recent_observations", [])]
    deltas = compare(obs, baseline, recent, datetime.now(UTC).date())
    rf = evaluate(
        RedFlagInput(
            observation=obs,
            vitals=None,
            baseline_vitals=baseline.vitals_usual,
            on_anticoagulant=profile.on_anticoagulant,
        )
    )
    raw = {
        **values.get("raw_input", {}),
        "turns": turns,
        "incidents": incidents,
        "seems_different": seems_different,
        "text": res.transcript,
    }
    new_state = {
        "raw_input": raw,
        "structured_observation": obs.model_dump(mode="json"),
        "baseline_delta": [d.model_dump(mode="json") for d in deltas],
        "red_flags": rf.model_dump(mode="json"),
        "asked_dimensions": res.asked_dimensions,
        "turn_count": res.turn_count,
        "caregiver_reports": [r.model_dump(mode="json") for r in res.reports],
        "updated_at": now_iso(),
    }
    new_state["caregiver_section"] = build_caregiver_section({**values, **new_state})
    with tagged(thread_id=thread_id, dialog_id=dialog_id):
        g.update_state(_config(thread_id), new_state, as_node=LIVE_REPORT_NODES[itype])
        g.invoke(
            None, _config(thread_id)
        )  # re-runs the interrupt node so the nurse sees fresh data
    _ = Profile, Baseline
    return {"dialog": res.model_dump(mode="json"), "snapshot": snapshot(thread_id)}


def start_stream(graph: str, patient_id: str, input_values: dict[str, Any]):
    """Like start(), but yields ('event', {...}) per node/agent step, then ('done', snapshot)."""
    tid = new_thread_id(graph, patient_id)
    registry.upsert(tid, graph=graph, patient_id=patient_id, status="running")
    dialog_id = (input_values.get("raw_input") or {}).get("dialog_id")
    with tagged(thread_id=tid, dialog_id=dialog_id):
        for mode, chunk in compiled(graph).stream(
            {**input_values, "patient_id": patient_id, "thread_id": tid},
            _config(tid),
            stream_mode=["custom", "updates"],
        ):
            if mode == "custom":
                yield "event", chunk
            else:
                for node, upd in chunk.items():
                    if node == "__interrupt__":
                        continue
                    yield (
                        "event",
                        {
                            "type": "node_end",
                            "name": node,
                            "summary": node,
                            "plain": node,
                            "patient_id": (upd or {}).get("patient_id")
                            if isinstance(upd, dict)
                            else None,
                        },
                    )
    yield "done", snapshot(tid)
